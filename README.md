# Raddai Metropolitan School - Django REST API Backend

A comprehensive Django REST API backend for Raddai Metropolitan School management system supporting multiple user roles with JWT authentication.

## Features

- **Multi-role Authentication**: Admin, Management, Staff, Student, Parent roles
- **JWT Token Authentication**: Secure API access with refresh tokens
- **Role-based Permissions**: Different access levels for different user types
- **Comprehensive Models**: Academic years, classes, subjects, results, fees, attendance, announcements
- **CORS Enabled**: Ready for Next.js frontend integration

## Tech Stack

- **Django 6.0.1**
- **Django REST Framework** - API framework
- **JWT Authentication** - Token-based auth
- **PostgreSQL** - Database (SQLite for development)
- **CORS Headers** - Cross-origin support

## Installation & Setup

### Prerequisites
- Python 3.8+
- pip
- virtualenv (recommended)

### Setup Steps

1. **Clone and navigate to the backend directory**
   ```bash
   cd raddai-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # On Windows
   # or
   source venv/bin/activate     # On macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install django djangorestframework djangorestframework-simplejwt django-cors-headers psycopg2-binary
   ```

4. **Run migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create sample data (optional)**
   ```bash
   python manage.py shell -c "
   # Copy and paste the sample data creation script from the setup
   "
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

The API will be available at `http://127.0.0.1:8000/api/`

## API Endpoints

### Authentication
- `POST /api/auth/login/` - User login
- `POST /api/auth/token/refresh/` - Refresh access token (DRF built-in)

### Dashboard
- `GET /api/dashboard/stats/` - Dashboard statistics (role-based)

### Core Resources

#### Users
- `GET /api/users/` - List users (filtered by role)
- `GET /api/users/{id}/` - Get user details
- `PATCH /api/users/profile/` - Update current user profile

#### Academic Management
- `GET /api/academic-years/` - List academic years
- `GET /api/classes/` - List classes
- `GET /api/subjects/` - List subjects
- `GET /api/results/` - List results (filtered by user role)
- `POST /api/results/` - Create result (staff only)
- `GET /api/attendance/` - List attendance records

#### Fee Management
- `GET /api/fee-structures/` - List fee structures
- `GET /api/fee-payments/` - List fee payments (filtered by user)

#### Communication
- `GET /api/announcements/` - List announcements (filtered by audience)

#### User Profiles
- `GET /api/students/` - List students
- `GET /api/staff/` - List staff
- `GET /api/parents/` - List parents

## User Roles & Permissions

### Admin
- Full system access
- Can manage all resources
- User role management

### Management
- School-wide analytics and reports
- Can view all students, staff, parents
- Financial overview
- Announcement management

### Staff (Teachers)
- View assigned classes/subjects
- Upload/manage results for assigned classes
- View student performance
- Mark attendance (future feature)
- Communication with parents/students

### Students
- View personal academic results
- Access attendance records
- View fee payment status
- Personal profile management

### Parents
- View children's academic results
- Monitor children's attendance
- Fee payment status for children
- Receive school announcements

## Sample API Usage

### 1. Login
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Response:
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 2,
    "username": "admin",
    "role": "admin",
    "full_name": "School Admin"
  }
}
```

### 2. Get Dashboard Stats (with auth token)
```bash
curl -X GET http://127.0.0.1:8000/api/dashboard/stats/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Get User Profile
```bash
curl -X GET http://127.0.0.1:8000/api/users/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Sample User Credentials

After running the sample data script, you can use these credentials:

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Management | management | mgmt123 |
| Staff | teacher1 | teacher123 |
| Student | student1 | student123 |
| Parent | parent1 | parent123 |

## Data Models

### Core Models
- **User**: Custom user model with roles
- **AcademicYear**: Academic year management
- **Class**: School classes/grades
- **Subject**: Academic subjects
- **Student**: Student profiles
- **Staff**: Staff/teacher profiles
- **Parent**: Parent profiles with children relationships

### Academic Models
- **Result**: Academic results/grades
- **Attendance**: Student attendance records

### Financial Models
- **FeeStructure**: Fee definitions by grade/year
- **FeePayment**: Payment records and status

### Communication
- **Announcement**: School announcements with target audiences

## Security Features

- JWT token authentication
- Role-based access control
- CORS configuration for frontend integration
- Input validation and sanitization
- SQL injection protection (Django ORM)

## Development

### Running Tests
```bash
python manage.py test
```

### Code Formatting
```bash
# Install black and isort for code formatting
pip install black isort
black .
isort .
```

### Database Schema Changes
```bash
python manage.py makemigrations
python manage.py migrate
```

## Deployment

### Environment Variables
Create a `.env` file with:
```
DEBUG=False
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
ALLOWED_HOSTS=your-domain.com
```

### Production Settings
- Use PostgreSQL instead of SQLite
- Set DEBUG=False
- Configure proper ALLOWED_HOSTS
- Use environment variables for secrets
- Set up proper logging
- Configure static files serving

## API Documentation

The API is built with Django REST Framework, which provides automatic API documentation at:
- `http://127.0.0.1:8000/api/` - API root with browsable interface
- Each endpoint provides detailed information about parameters, responses, and authentication requirements

## Integration with Next.js Frontend

The API is designed to work seamlessly with the Next.js frontend:

1. **CORS**: Already configured for `http://localhost:3000`
2. **JWT Tokens**: Use refresh tokens to maintain sessions
3. **Role-based UI**: Frontend can use the `role` field to show appropriate interfaces
4. **Error Handling**: Consistent error responses for frontend handling

## Contributing

1. Follow Django best practices
2. Write tests for new features
3. Update documentation
4. Use meaningful commit messages
5. Ensure all endpoints work with different user roles

## License

This project is part of the Raddai Metropolitan School Management System and follows the same licensing terms as the main project.