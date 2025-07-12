# Holokai Web Scheduler

A comprehensive academic planning tool for BYU-Hawaii students to create and manage their college course schedules. The system helps students plan their academic path by selecting majors, minors, and tracking their progress through different Holokai sections.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [File Structure](#file-structure)
- [Technologies Used](#technologies-used)
- [Contributing](#contributing)

## Features

### Student Features
- **Dual Planning Modes**: Create academic plans either by number of semesters or by credits per semester
- **Holokai Integration**: Automatically ensures students select courses from different Holokai sections (Arts & Humanities, Professional Studies, Math & Sciences)
- **Schedule Generation**: AI-powered schedule optimization using machine learning algorithms
- **Plan Modification**: Change existing academic plans and see updated schedules
- **Course Search**: Search and browse available courses, majors, and minors
- **Class Details**: View detailed information about classes including prerequisites, corequisites, and descriptions
- **Credit Tracking**: Monitor total credits and graduation requirements

### Administrative Features
- **Course Management**: Add, edit, and delete courses
- **Class Management**: Manage individual classes within courses
- **Section Management**: Organize classes into required and elective sections
- **Drag & Drop**: Reorder course sections with intuitive interface
- **Bulk Operations**: Import/export course data
- **Real-time Updates**: Live statistics on courses, classes, and academic programs

## Architecture

The application follows a modern web architecture with the following components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   ML Service   │
│   (HTML/CSS/JS) │◄──►│   (Node.js)     │◄──►│   (Python)      │
│                 │    │                 │    │                 │
│ • User Interface│    │ • REST API      │    │ • Schedule AI   │
│ • Form Handling │    │ • Database      │    │ • Optimization  │
│ • AJAX Requests │    │ • File Serving  │    │ • Constraints   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   PostgreSQL    │
                       │   Database      │
                       └─────────────────┘
```

## Installation

### Prerequisites
- Node.js (v14 or higher)
- PostgreSQL database
- Python 3.8+ (for ML service)
- Docker (optional, for containerized deployment)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Course-Scheduler-New
   ```

2. **Install Node.js dependencies**
   ```bash
   npm install
   ```

3. **Set up the database**
   - Create a PostgreSQL database
   - Run the initialization script: `db/init.sql`

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

5. **Set up ML service**
   ```bash
   cd ml_trainer
   pip install -r requirements.txt
   ```

6. **Start the application**
   ```bash
   # Start main server
   npm start
   
   # Start ML service (in separate terminal)
   cd ml_trainer
   python api.py
   ```

### Docker Deployment

```bash
docker-compose up -d
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```properties
PORT=3000
DATABASE_URL=postgresql://username:password@host:port/database
ML_SERVICE_URL=http://ml_service:5000
```

### Database Configuration

The application uses PostgreSQL with the following key tables:
- `courses` - Academic courses (majors, minors, etc.)
- `classes` - Individual classes within courses
- `course_sections` - Organizational sections within courses
- `classes_in_course` - Relationship between classes and courses

## Usage

### For Students

1. **Getting Started**
   - Visit the homepage at `http://localhost:3000`
   - Choose between semester-based or credit-based planning

2. **Creating a Schedule**
   - Select your major and two minors from different Holokai sections
   - Choose your starting semester and academic level
   - Click "Generate Schedule" to create your academic plan

3. **Modifying Plans**
   - Use the "Change Your Plan" feature to update existing schedules
   - Add or remove classes from specific semesters
   - View updated graduation timeline

### For Administrators

1. **Course Management**
   - Access admin features through the search interface
   - Add new courses with appropriate metadata
   - Organize classes into sections (required/elective)

2. **Class Management**
   - Add individual classes to courses
   - Set prerequisites and corequisites
   - Configure semester availability and restrictions

## API Documentation

### Course Endpoints

```
GET    /api/courses              # Get all courses
POST   /api/courses              # Create new course
GET    /api/courses/:id          # Get specific course
PUT    /api/courses/:id          # Update course
DELETE /api/courses/:id          # Delete course
```

### Class Endpoints

```
GET    /api/classes              # Get all classes
POST   /api/classes              # Create new class
GET    /api/classes/:id          # Get specific class
PUT    /api/classes/:id          # Update class
DELETE /api/classes/:id          # Delete class
GET    /api/classes/search       # Search classes
```

### Section Endpoints

```
GET    /api/courses/:id/sections           # Get course sections
POST   /api/courses/:id/sections           # Create section
PUT    /api/courses/:id/sections/:section_id  # Update section
DELETE /api/courses/:id/sections/:section_id  # Delete section
```

### ML Service Endpoints

```
POST   /api/generate-schedule    # Generate optimized schedule
POST   /api/optimize-plan        # Optimize existing plan
```

## File Structure

```
Course-Scheduler-New/
├── public/                     # Frontend files
│   ├── css/                   # Stylesheets
│   │   ├── styles.css         # Main styles
│   │   ├── admin.css          # Admin interface styles
│   │   ├── course_details.css # Course detail page styles
│   │   └── components.css     # Shared component styles
│   ├── js/                    # JavaScript files
│   │   ├── script.js          # Main application logic
│   │   ├── course_details.js  # Course management
│   │   ├── add_course.js      # Course creation
│   │   └── search.js          # Search functionality
│   ├── assets/                # Images and icons
│   └── *.html                 # HTML pages
├── routes/                    # Express.js routes
│   └── api.js                 # API endpoints
├── ml_trainer/                # Machine learning service
│   ├── api.py                 # ML API server
│   ├── constraint_optimizer.py # Schedule optimization
│   ├── data_processor.py      # Data processing
│   └── requirements.txt       # Python dependencies
├── db/                        # Database files
│   └── init.sql              # Database schema
├── server.js                  # Main application server
├── db.js                      # Database connection
├── package.json              # Node.js dependencies
├── docker-compose.yml        # Docker configuration
└── README.md                 # This file
```

## Technologies Used

### Frontend
- **HTML5/CSS3**: Modern web standards
- **Vanilla JavaScript**: No framework dependencies
- **Responsive Design**: Mobile-friendly interface
- **Drag & Drop API**: Interactive course management

### Backend
- **Node.js**: Runtime environment
- **Express.js**: Web framework
- **PostgreSQL**: Primary database
- **RESTful API**: Standard HTTP methods

### Machine Learning
- **Python**: ML service language
- **Custom Algorithms**: Schedule optimization
- **Constraint Solving**: Academic requirement validation

### Deployment
- **Docker**: Containerization
- **Docker Compose**: Multi-service orchestration

## Key Features Detail

### Holokai System Integration
The application enforces BYU-Hawaii's Holokai requirement where students must complete courses from three different academic sections:
- Arts & Humanities (Red indicator)
- Professional Studies (Silver indicator)  
- Math & Sciences (Gold indicator)

### AI-Powered Scheduling
The ML service provides:
- Prerequisite validation
- Credit distribution optimization
- Semester availability checking
- Graduation timeline optimization

### Responsive Design
- Mobile-first approach
- Tablet and desktop optimization
- Touch-friendly interface
- Accessible design patterns

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

### Development Guidelines

- Follow existing code style and conventions
- Add comments for complex logic
- Test all new features thoroughly
- Update documentation as needed
- Ensure responsive design compatibility

## License

This project is developed for BYU-Hawaii's academic planning system.

## Support

For technical issues or feature requests, please contact the development team or create an issue in the repository.

---

**Note**: This application is specifically designed for BYU-Hawaii's academic structure and Holokai requirements. Customization may be needed for other institutions.

