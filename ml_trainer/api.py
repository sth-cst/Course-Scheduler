from flask import Flask, request, jsonify
from flask_cors import CORS
from constraint_optimizer import ScheduleOptimizer
from data_processor import ScheduleDataProcessor
import os
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://course-scheduler-web.onrender.com",  # Production
            "http://localhost:3000",  # Local development
            "http://web:3000"  # Docker development
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

optimizer = ScheduleOptimizer()
data_processor = ScheduleDataProcessor()

# Add health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "course-scheduler-ml",
        "timestamp": str(datetime.now())
    })

@app.route('/generate-schedule', methods=['POST'])
def generate_schedule():
    """Generate a course schedule based on provided requirements"""
    try:
        print("Received request at /generate-schedule")
        data = request.json
        print(f"Request payload: {data}")
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        processed_data = data_processor.process_payload(data)
        schedule_result = optimizer.create_schedule(processed_data)
        
        print(f"Generated schedule successfully")
        return jsonify(schedule_result)
        
    except Exception as e:
        print(f"Error generating schedule: {str(e)}")
        return jsonify({
            "error": str(e),
            "metadata": {
                "success": False
            }
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)