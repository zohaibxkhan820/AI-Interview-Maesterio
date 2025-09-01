import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Interview
from .ai_interviewer import AIInterviewer

class InterviewConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.interview_id = self.scope['url_route']['kwargs']['interview_id']
        self.room_group_name = f'interview_{self.interview_id}'
        self.ai_interviewer = None

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'start_listening':
                # Notify the backend to start listening
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'interview.message',
                        'message': {
                            'type': 'start_listening'
                        }
                    }
                )
            elif message_type == 'stop_listening':
                # Notify the backend to stop listening
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'interview.message',
                        'message': {
                            'type': 'stop_listening'
                        }
                    }
                )
            elif message_type == 'voice_data':
                # Handle incoming voice data
                voice_data = text_data_json.get('data')
                if voice_data:
                    # Process voice data and convert to text
                    text = await self.process_voice_data(voice_data)
                    if text:
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'interview.message',
                                'message': {
                                    'type': 'voice_text',
                                    'text': text
                                }
                            }
                        )
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e)
            }))

    async def interview_message(self, event):
        """Send message to WebSocket."""
        await self.send(text_data=json.dumps(event['message']))

    @database_sync_to_async
    def process_voice_data(self, voice_data):
        """Process voice data and convert to text."""
        try:
            # Get the AI interviewer instance
            from .ai_interview_views import ai_interviewers
            ai_interviewer = ai_interviewers.get(self.interview_id)
            
            if ai_interviewer and ai_interviewer.voice_manager:
                # Convert voice data to text using the voice manager
                text = ai_interviewer.voice_manager.process_voice_data(voice_data)
                return text
        except Exception as e:
            print(f"Error processing voice data: {e}")
            return None 