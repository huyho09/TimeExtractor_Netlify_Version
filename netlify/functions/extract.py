import json
import re
import os
import io
import base64
import traceback # For detailed error logging
from datetime import datetime, time
from pypdf import PdfReader
from numbers import Number # Imported from original views.py

# --- InOutHandle Class ---
# (This class is unchanged)
class InOutHandle():
    time_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}$')    
    def findTimeIn(self,array):
        time_in = None
        for item_val in array: 
            if isinstance(item_val, str) and self.time_pattern.match(item_val):
                time_in = item_val
                break
        return time_in

    def findTimeOut(self,array): 
        time_out = None
        for item_val in reversed(array):
            if isinstance(item_val, str) and self.time_pattern.match(item_val): 
                time_out = item_val
                break
        return time_out 

    def calculateDuration(self,time_in,time_out):
        try:
            time_in_obj = datetime.strptime(time_in,'%H:%M:%S')
            time_out_obj = datetime.strptime(time_out,'%H:%M:%S')
        except ValueError as e:
            print(f"Error parsing time in calculateDuration: {e}. time_in='{time_in}', time_out='{time_out}'")
            return 0
        
        noon_time = time(12, 0, 0)
        duration_seconds = (time_out_obj - time_in_obj).total_seconds()
       
        if time_in_obj.time() < noon_time and time_out_obj.time() < noon_time:
            duration_hours = (duration_seconds / 3600)
        else:
            duration_hours = (duration_seconds / 3600) - 1

        if duration_hours <= 0 : 
            duration_hours = 0.0 
        elif duration_hours > 10: 
            duration_hours = 10.0 
        return round(duration_hours, 2)

    def count_all_time(self, all_time_dict_data):
        leave_total = 0.0 
        if not isinstance(all_time_dict_data, list): 
            print("Warning: count_all_time received non-list data.")
            return leave_total

        for item_record in all_time_dict_data: 
            if not isinstance(item_record, dict): 
                print(f"Warning: count_all_time found non-dict item: {item_record}")
                continue
            
            paid_hours_str = item_record.get('paidHours', '0,00') 
            
            if isinstance(paid_hours_str, str) and paid_hours_str != '0,00': 
                try:
                    leave_total += float(paid_hours_str.replace(',', '.'))
                except ValueError:
                    print(f"Warning: Could not convert paidHours '{paid_hours_str}' to float.")
            elif isinstance(paid_hours_str, (int, float)) and paid_hours_str != 0:
                 leave_total += float(paid_hours_str)

        return round(leave_total, 2)
    
    def calculate_flex_total(self, all_time_dict_data):
        total_flex_hours = 0.0
        
        if not isinstance(all_time_dict_data, list): 
            print("Warning: calculate_flex_total received non-list data.")
            return total_flex_hours

        for item_record in all_time_dict_data: 
            if not isinstance(item_record, dict): 
                print(f"Warning: calculate_flex_total found non-dict item: {item_record}")
                continue
            
            actual_hours = item_record.get('actualWorkingHours', 0.0)
            
            if not isinstance(actual_hours, (int, float)):
                actual_hours = 0.0

            if actual_hours > 0:
                value_to_add = actual_hours - 8.0
            else:
                value_to_add = 0.0
            
            total_flex_hours += value_to_add

        return round(total_flex_hours, 2)

# --- PdfHandler Class ---
# (This class is unchanged)
class PdfHandler():
    def __init__(self, file_bytes) :
        self.file_bytes = file_bytes

    def extractText(self):
        reader = PdfReader(io.BytesIO(self.file_bytes))
        time_array = []
        for _,page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                for line in lines: 
                    a = self.extractTime(line)
                    if a: 
                        time_array.append(a)
        return time_array
    
    def extractTime(self, line: str):
        new_array = []
        filter_array = ["01","02","03","04","05","06","07","08","09","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24","25","26","27","28","29","30","31","32"]
        if len(line) >= 2:  
            compare_character = line[0] + line[1]
            for item_filter in filter_array:
                if item_filter in compare_character:
                    new_array.append(line)
                    break
        return new_array

    def breakArray(self): 
        time_array = self.extractText()
        new_time_array = []
        for item_list in time_array: 
            if item_list:
                res = ''.join(item_list) 
                element = res.split(' ') 
                temp_array = [val for val in element if val] 
                new_time_array.append(temp_array)
        if new_time_array: 
            new_time_array.pop(0) 
        return new_time_array
    
    def convertToDict(self): 
        new_time_array = self.breakArray()
        all_time_dict = []
        total_duration_sum = 0 
        worked_day = 0
        total_adjusted_hours = 0.0 
        
        timeHandle = InOutHandle()

        for item_data_list in new_time_array: 
            message:str = ''
            actual_working_hour:float = 0
            time_in = timeHandle.findTimeIn(item_data_list)
            time_out = timeHandle.findTimeOut(item_data_list)
            
            duration = 0
            if time_in is not None and time_out is not None:
                duration = timeHandle.calculateDuration(time_in,time_out)
                message = f"Duration: {duration:.2f} from {time_in} to {time_out}"
                actual_working_hour = round(duration, 2)
                worked_day += 1 
                total_duration_sum += duration 
            elif time_in is not None and time_out is None: 
                message = "Maybe you forgot to Check-Out"
            elif time_in is None and time_out is not None:
                message = "Maybe you forgot to Check-In"
            elif time_in is None and time_out is None: 
                if len(item_data_list) > 5 and (item_data_list[3] == "BusinessReason" or item_data_list[3] == "Work"): 
                    message = item_data_list[3] + " " + item_data_list[4] + " " + item_data_list[5]
                elif len(item_data_list) > 4 and item_data_list[3] == "Annual": 
                    message = item_data_list[3] +" "+ item_data_list[4]
                else: 
                    message = "Not Worked"
            
            if len(item_data_list) >= 4 and item_data_list[-4] == "8,00":
                actual_working_hour = 8.00
            
            if len(item_data_list) >= 8:  
                time_dict = {
                    "date": item_data_list[0] + ' ' + item_data_list[1] if len(item_data_list) > 1 else "N/A",
                    "dws": item_data_list[2] if len(item_data_list) > 2 else "N/A",
                    "timeIn": time_in,
                    "timeOut": time_out,
                    "otHour_leaveInLieu": item_data_list[-1],
                    "otHour_cashPayment": item_data_list[-2],
                    "unpaidHours": item_data_list[-3],
                    "paidHours": item_data_list[-4],
                    "missingHours": item_data_list[-5],
                    "nightShiftHours": item_data_list[-6],
                    "normalWorkingHours": item_data_list[-7],
                    "message": message,
                    "actualWorkingHours": actual_working_hour
                }
                all_time_dict.append(time_dict)
            else:
                print(f"Skipping item due to insufficient data: {item_data_list}")
        
        for i, record in enumerate(all_time_dict):
            if not isinstance(record, dict): continue
            normal_hours_str = record.get("normalWorkingHours")
            if normal_hours_str is None: continue

            try:
                cleaned_hours_str = normal_hours_str.replace(',', '.')
                hours = float(cleaned_hours_str)
            except (ValueError, AttributeError):
                if isinstance(normal_hours_str, (int, float)):
                    hours = float(normal_hours_str)
                else:
                    continue

            value_to_add = 0.0
            if hours >= 10:
                value_to_add = 2.0
            elif hours == 0 or hours == 8:
                value_to_add = 0.0
            else:
                value_to_add = hours - 8.0
                
            total_adjusted_hours += value_to_add
        
        leave_handle = InOutHandle()
        total_leave = leave_handle.count_all_time(all_time_dict)
        total_flex = leave_handle.calculate_flex_total(all_time_dict)
        total_month_summary = total_leave + total_duration_sum
        total_day_entries = len(all_time_dict)
        
        return {
            "time_dict": all_time_dict,
            "summary": {
                "total_leave": total_leave,
                "total_time": total_duration_sum,
                "total_day": total_day_entries,
                "worked_day": worked_day,
                "total_month": total_month_summary,
                "calculated_adjusted_hours": total_adjusted_hours,
                "total_flex": total_flex
            }
        }

# --- The main Netlify Function Handler (UPDATED) ---
def handler(event, context):
    
    # --- NEW: Handle CORS Preflight (OPTIONS request) ---
    # This is sent by the browser before the POST request to check permissions
    http_method = event.get('httpMethod')
    
    if http_method == 'OPTIONS':
        print("Received OPTIONS request, sending CORS headers.")
        return {
            'statusCode': 204, # 204 No Content
            'headers': {
                'Access-Control-Allow-Origin': '*', # Allow all origins
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': ''
        }

    # --- Handle POST request (Your original code) ---
    if http_method == 'POST':
        try:
            # 1. Parse the incoming request body
            body = json.loads(event.get('body', '{}'))
            file_data_base64 = body.get('file')

            if not file_data_base64:
                print("ERROR: No 'file' key found in JSON body.")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'No file data found in request.'})
                }

            # 2. Decode the Base64 file data into raw bytes
            print("File data found, attempting to decode Base64...")
            file_bytes = base64.b64decode(file_data_base64)
            print(f"Successfully decoded file, {len(file_bytes)} bytes.")

            # 3. Process the file in memory
            print("Starting PDF processing...")
            pdf_handler = PdfHandler(file_bytes)
            results = pdf_handler.convertToDict() 
            print("Successfully processed PDF and generated results.")

            # 4. Return the successful JSON response
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*' # Also add origin header to POST response
                },
                'body': json.dumps(results)
            }
            
        except Exception as e:
            # 5. CATCH THE CRASH
            print(f"!!! FUNCTION CRASHED !!!")
            print(f"Error: {e}")
            print(traceback.format_exc()) 
            
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f"Server error: {str(e)}",
                    'trace': traceback.format_exc() 
                })
            }

    # --- Handle other methods (like GET) ---
    print(f"Received unallowed method: {http_method}")
    return {
        'statusCode': 405,
        'headers': {
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': f"Method {http_method} Not Allowed"})
    }