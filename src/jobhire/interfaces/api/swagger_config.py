"""
Swagger/OpenAPI documentation configuration.
"""

from typing import Dict, Any


def get_openapi_config() -> Dict[str, Any]:
    """Get OpenAPI configuration for Swagger documentation."""
    return {
        "title": "ApplyRush.AI Backend API",
        "description": """
## 🚀 ApplyRush.AI Backend API

Enterprise-grade job application automation platform with AI-powered matching and automated application submission.

### 🔐 Authentication
All endpoints (except health checks) require authentication via Bearer token:
```
Authorization: Bearer <your_token>
```

### 📱 Features
- **AI-Powered Job Matching**: Advanced algorithms to match jobs to user preferences
- **Automated Applications**: Submit applications automatically based on user settings
- **Document Generation**: AI-generated cover letters and resume optimization (Premium)
- **Real-time Notifications**: Email and webhook notifications for application status
- **Queue Management**: Intelligent job application queue with priorities
- **Analytics**: Comprehensive job search and application analytics

### 💎 Premium Features
Some features require premium subscription:
- AI Cover Letter Generation
- AI Resume Optimization
- Advanced Analytics
- Priority Support

### 🏷️ API Endpoint Groups

#### 🔐 Authentication
- User registration, login, logout
- Password management
- Token refresh

#### 👥 User Management
- User CRUD operations
- Account activation/deactivation
- Tier upgrades

#### 👤 User Settings & Profile
- Comprehensive settings management
- Profile information
- Search preferences

#### ⚙️ Configuration Management
- Specific setting updates
- Match level configuration
- Document generation settings
- Approval mode configuration

#### 📦 Bulk Operations
- Save all settings at once
- Reset settings to defaults
- Settings validation

#### 🔧 Service Operations
- Start/stop/pause job search service
- Service status monitoring

#### 🔍 Job Search
- Execute job searches
- Search history and analytics
- Automated search scheduling

#### 📋 Job Queue
- Application queue management
- Priority handling
- Processing status tracking

#### 📱 Application Settings
- Application-specific configurations
- Notification preferences
- Premium feature access

#### 🔗 Webhooks & Callbacks
- Email processing webhooks
- Application status change notifications
- External service integrations

#### 💚 Health & Status
- API health monitoring
- Service status checks
- Database connectivity

### 📊 Response Format
All API responses follow a consistent format:
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 🚨 Error Handling
Error responses include detailed information:
```json
{
  "detail": "Error description",
  "type": "error_type",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 🔒 Security
- JWT-based authentication
- Role-based access control (RBAC)
- API rate limiting
- Input validation and sanitization
- Webhook signature verification

### 📈 Monitoring
- Request/response logging
- Performance metrics
- Error tracking
- Health monitoring

### 🌐 Environment
- **Production**: `https://api.applyrush.ai/v1`
- **Staging**: `https://staging-api.applyrush.ai/v1`
- **Development**: `http://localhost:8000/api/v1`
        """,
        "version": "1.0.0",
        "contact": {
            "name": "ApplyRush.AI Support",
            "email": "support@applyrush.ai",
            "url": "https://applyrush.ai/support"
        },
        "license": {
            "name": "Proprietary",
            "url": "https://applyrush.ai/license"
        },
        "servers": [
            {
                "url": "https://api.applyrush.ai/v1",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.applyrush.ai/v1",
                "description": "Staging server"
            },
            {
                "url": "http://localhost:8000/api/v1",
                "description": "Development server"
            }
        ],
        "tags": [
            {
                "name": "🔐 Authentication",
                "description": "User authentication and authorization endpoints"
            },
            {
                "name": "👥 User Management",
                "description": "User account management (Admin operations)"
            },
            {
                "name": "👤 User Settings",
                "description": "Comprehensive user settings management"
            },
            {
                "name": "👤 User Profile",
                "description": "User profile information and management"
            },
            {
                "name": "⚙️ Specific Configuration",
                "description": "Individual setting configuration endpoints"
            },
            {
                "name": "📦 Bulk Operations",
                "description": "Bulk settings operations and validation"
            },
            {
                "name": "🔧 Service Operations",
                "description": "Job search service control and monitoring"
            },
            {
                "name": "🔍 Job Search",
                "description": "Job search execution and management"
            },
            {
                "name": "📋 Job Queue",
                "description": "Application queue management and processing"
            },
            {
                "name": "📱 Application Settings",
                "description": "Application-specific settings and preferences"
            },
            {
                "name": "🔗 Webhooks & Callbacks",
                "description": "External webhooks and callback handlers"
            },
            {
                "name": "💚 Health & Status",
                "description": "System health monitoring and status checks"
            }
        ]
    }


def get_swagger_ui_parameters() -> Dict[str, Any]:
    """Get Swagger UI customization parameters."""
    return {
        "swagger_ui_parameters": {
            "deepLinking": True,
            "displayRequestDuration": True,
            "docExpansion": "none",
            "operationsSorter": "alpha",
            "filter": True,
            "tagsSorter": "alpha",
            "tryItOutEnabled": True,
            "persistAuthorization": True,
            "layout": "BaseLayout",
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 2,
            "displayOperationId": False,
            "showExtensions": True,
            "showCommonExtensions": True
        }
    }


def get_redoc_parameters() -> Dict[str, Any]:
    """Get ReDoc customization parameters."""
    return {
        "redoc_ui_parameters": {
            "expandResponses": "200,201",
            "hideDownloadButton": False,
            "hideHostname": False,
            "hideLoading": False,
            "menuToggle": True,
            "nativeScrollbars": False,
            "noAutoAuth": False,
            "pathInMiddlePanel": True,
            "requiredPropsFirst": True,
            "scrollYOffset": 0,
            "showExtensions": True,
            "sortPropsAlphabetically": True,
            "theme": {
                "colors": {
                    "primary": {
                        "main": "#3b82f6"
                    }
                },
                "typography": {
                    "fontSize": "14px",
                    "lineHeight": "1.5em",
                    "code": {
                        "fontSize": "13px"
                    },
                    "headings": {
                        "fontFamily": "system-ui, -apple-system, sans-serif",
                        "fontWeight": "600"
                    }
                },
                "sidebar": {
                    "width": "260px",
                    "backgroundColor": "#fafafa"
                },
                "rightPanel": {
                    "backgroundColor": "#263238",
                    "width": "40%"
                }
            }
        }
    }