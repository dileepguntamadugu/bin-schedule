from flask import Flask, request, jsonify
import requests
from ics import Calendar, Event
import resend
import os
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
# Get your API Key for free at https://resend.com
resend.api_key = os.environ.get("RESEND_API_KEY") 

@app.route('/api/send-calendar', methods=['POST'])
def send_calendar():
    data = request.json
    user_address = data.get('address')
    user_email = data.get('email')

    if not user_address or not user_email:
        return jsonify({"error": "Address and Email are required"}), 400

    try:
        # 1. FETCH SCHEDULE (The logic we reversed engineered)
        headers = {"User-Agent": "Mozilla/5.0"}
        search_resp = requests.get("https://thehills.waste-info.com.au/api/v1/properties", 
                                   params={"q": user_address}, headers=headers)
        search_data = search_resp.json()
        
        if not search_data['properties']:
            return jsonify({"error": "Address not found"}), 404

        prop_id = search_data['properties'][0]['id']
        schedule_resp = requests.get(f"https://thehills.waste-info.com.au/api/v1/properties/{prop_id}.json", 
                                     headers=headers)
        schedule_data = schedule_resp.json()

        # 2. GENERATE ICS
        c = Calendar()
        for service in schedule_data.get('services', []):
            waste_type = service.get('name')
            emoji = "🗑️"
            if "Garbage" in waste_type: emoji = "🔴"
            elif "Recycling" in waste_type: emoji = "🟡"
            elif "Garden" in waste_type: emoji = "🟢"

            for item in service.get('events', []):
                e = Event()
                e.name = f"{emoji} {waste_type}"
                e.begin = item.get('date')
                e.make_all_day()
                c.events.add(e)

        ics_content = c.serialize()

        # 3. SEND EMAIL (Using Resend)
        # Note: You can only send to yourself on the free tier until you verify a domain.
        # Ideally, verify a domain like 'mybintool.com' or just use the "Download" option below.
        params = {
            "from": "Bin Bot <onboarding@resend.dev>",
            "to": [user_email],
            "subject": "Your 2026 Bin Calendar",
            "html": "<strong>Here is your bin calendar!</strong> Drag the attached file into Google Calendar.",
            "attachments": [
                {"filename": "bin_schedule.ics", "content": list(ics_content.encode('utf-8'))}
            ]
        }
        resend.Emails.send(params)

        return jsonify({"success": True, "message": "Calendar emailed!"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Vercel requires this
if __name__ == '__main__':
    app.run()