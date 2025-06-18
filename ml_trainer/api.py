from flask import Flask, request, jsonify
from flask_cors import CORS
from constraint_optimizer import ScheduleOptimizer
from data_processor import ScheduleDataProcessor
import os
from datetime import datetime
import logging

app = Flask(__name__)
# Update CORS configuration
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://course-scheduler-web.onrender.com",
            "http://localhost:3000",
            "http://web:3000",
            "*"  # Temporarily allow all origins for testing
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Origin"],
        "expose_headers": ["Content-Type", "Authorization"]
    }
})

optimizer = ScheduleOptimizer()
data_processor = ScheduleDataProcessor()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "course-scheduler-ml",
        "timestamp": str(datetime.now())
    })

@app.route('/ping', methods=['GET'])
def ping():
    """Health check endpoint with more details"""
    return jsonify({
        "status": "healthy",
        "service": "course-scheduler-ml",
        "timestamp": str(datetime.now()),
        "env": os.environ.get('FLASK_ENV', 'unknown'),
        "port": os.environ.get('PORT', 'unknown')
    })

@app.route('/generate-schedule', methods=['POST', 'OPTIONS'])
def generate_schedule():
    """Generate a course schedule based on provided requirements"""
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        logger.info("=== Received Schedule Generation Request ===")
        logger.info(f"Request Headers: {dict(request.headers)}")
        logger.info(f"Origin: {request.headers.get('Origin', 'No origin')}")
        logger.info(f"Content-Type: {request.headers.get('Content-Type')}")
        
        data = request.json
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No data provided"}), 400
            
        logger.info(f"Request Payload: {data}")
        
        processed_data = data_processor.process_payload(data)
        schedule_result = optimizer.create_schedule(processed_data)
        
        logger.info("Schedule generated successfully")
        logger.info(f"Response: {schedule_result}")
        return jsonify(schedule_result)
        
    except Exception as e:
        logger.exception("Error in generate_schedule:")
        return jsonify({
            "error": str(e),
            "metadata": {
                "success": False,
                "timestamp": str(datetime.now())
            }
        }), 500

@app.route('/test-connection', methods=['POST'])
def test_connection():
    """Test endpoint to verify connection and payload handling"""
    try:
        logger.info("=== Test Connection Request ===")
        logger.info(f"Headers: {dict(request.headers)}")
        data = request.json
        
        return jsonify({
            "status": "success",
            "received_data": data,
            "timestamp": str(datetime.now()),
            "headers_received": dict(request.headers)
        })
    except Exception as e:
        logger.exception("Error in test connection:")
        return jsonify({"error": str(e)}), 500

@app.route('/test-payload', methods=['POST'])
def test_payload():
    """Test endpoint for payload validation"""
    try:
        data = request.json
        logger.info("=== Test Payload Request ===")
        logger.info(f"Received payload with {len(data.get('courseData', []))} courses")
        logger.info(f"Preferences: {data.get('preferences', {})}")
        
        # Validate key components
        course_data = data.get('courseData', [])
        preferences = data.get('preferences', {})
        
        return jsonify({
            "status": "success",
            "payload_size": len(str(data)),
            "courses_count": len(course_data),
            "preferences": preferences,
            "timestamp": str(datetime.now())
        })
    except Exception as e:
        logger.exception("Error in test payload:")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)