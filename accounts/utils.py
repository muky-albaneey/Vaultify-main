import requests
import os
FCM_API_KEY = os.getenv("FCM_API_KEY")

# FCM_API_KEY = 'YOUR_FIREBASE_SERVER_KEY'

def send_fcm_notification(token, title, body):
    url = 'https://fcm.googleapis.com/fcm/send'
    headers = {
        'Authorization': f'key={FCM_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'to': token,
        'notification': {
            'title': title,
            'body': body,
        },
        'priority': 'high'
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()
