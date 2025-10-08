# Upselling Endpoints - Authentication Migration

## ✅ Migrated to Authenticated Endpoints

All upselling endpoints now require authentication using JWT tokens.

## 🔒 Changes Made

### Before (Insecure):
```python
# Required email in request body
class UpdateProfileRequest(BaseModel):
    email: EmailStr  # ❌ User could fake email
    data: Dict[str, Any]

@router.post("/update-profile")
async def update_profile(request: UpdateProfileRequest):
    # Uses email from request (insecure)
    await mongodb_service.update_user_profile(
        email=request.email,
        profile_data=request.data
    )
```

### After (Secure):
```python
# Email NOT in request - comes from auth token
class UpdateProfileRequest(BaseModel):
    data: Dict[str, Any]  # ✅ No email needed

@router.post("/update-profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Authenticated
):
    # Uses email from authenticated user (secure)
    email = current_user.get("email")
    await mongodb_service.update_user_profile(
        email=email,
        profile_data=request.data
    )
```

## 📋 Updated Endpoints

### 1. Update Profile
```http
POST /api/v1/upselling/update-profile
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "full_name": "John Doe",
  "data": {
    "phone": "+1-555-0100",
    "location": "San Francisco, CA"
  }
}
```

### 2. Save Onboarding Step
```http
POST /api/v1/upselling/save-step
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "step": "job_preferences",
  "data": {
    "desired_positions": ["Software Engineer"],
    "preferred_locations": ["Remote"]
  }
}
```

### 3. Get User Profile
```http
GET /api/v1/upselling/user-profile
Authorization: Bearer {jwt_token}
```

### 4. Complete Onboarding
```http
POST /api/v1/upselling/complete-onboarding
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "step": "final",
  "data": {
    "preferences_set": true
  }
}
```

## 🔑 How to Use

### Step 1: User Logs In
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "user_id",
    "email": "user@example.com"
  }
}
```

### Step 2: Use Token in Upselling Endpoints
```http
POST /api/v1/upselling/save-step
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "step": "preferences",
  "data": {...}
}
```

## 🎯 Benefits

### Security:
- ✅ **No Email Spoofing** - Email comes from verified JWT token
- ✅ **User Authentication** - All requests verified
- ✅ **Token Expiration** - Sessions expire automatically
- ✅ **Rate Limiting** - Can limit by authenticated user

### UX:
- ✅ **Simpler Requests** - No need to pass email in every request
- ✅ **Consistent Auth** - Same pattern as other endpoints
- ✅ **Session Management** - Frontend manages one token

## 📊 Endpoint Comparison

| Endpoint | Before | After |
|----------|--------|-------|
| `/update-profile` | ❌ Email in body | ✅ Auth required |
| `/save-step` | ❌ Email in body | ✅ Auth required |
| `/user-profile` | ❌ Email in query | ✅ Auth required |
| `/complete-onboarding` | ❌ Email in body | ✅ Auth required |

## 🔧 Frontend Integration

### Before:
```typescript
// Had to pass email every time
const saveStep = async (email: string, step: string, data: any) => {
  await fetch('/api/v1/upselling/save-step', {
    method: 'POST',
    body: JSON.stringify({ email, step, data })
  });
};
```

### After:
```typescript
// Just use stored token
const saveStep = async (step: string, data: any) => {
  await fetch('/api/v1/upselling/save-step', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`
    },
    body: JSON.stringify({ step, data })
  });
};
```

## ⚠️ Breaking Changes

### Request Schema Changes:

1. **UpdateProfileRequest** - Removed `email` field
2. **OnboardingStepRequest** - Removed `email` field
3. **UploadResumeRequest** - Removed `email` field
4. **CompanyPreferencesRequest** - Removed `email` field
5. **CreatePasswordRequest** - Removed `email` field

### Frontend Must:
1. Store JWT token after login
2. Include token in Authorization header
3. Remove email from request bodies
4. Handle 401 Unauthorized errors

## 🧪 Testing

### Test Authentication:
```bash
# 1. Login to get token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}' \
  | jq -r '.access_token')

# 2. Use token in upselling endpoint
curl -X POST http://localhost:8000/api/v1/upselling/save-step \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "preferences",
    "data": {"location": "Remote"}
  }'
```

## 📈 Migration Impact

### Secure:
- ✅ All upselling endpoints now authenticated
- ✅ No risk of email spoofing
- ✅ Consistent auth pattern

### Compatible with:
- ✅ Subscription endpoints (already authenticated)
- ✅ Resume endpoints (already authenticated)
- ✅ Application endpoints (already authenticated)
- ✅ User settings endpoints (already authenticated)

## 📝 Notes

1. **Guest Users**: For pre-auth flows, use separate guest endpoints:
   - `/api/v1/resumes/upload-guest` - For resume upload before signup
   - `/api/v1/onboarding/guest` - For guest onboarding data

2. **Token Storage**: Frontend should:
   - Store token in `localStorage` or `sessionStorage`
   - Include in all authenticated requests
   - Clear on logout
   - Refresh before expiration

3. **Error Handling**:
   - `401 Unauthorized` - Token invalid/expired, redirect to login
   - `403 Forbidden` - User doesn't have permission
   - `404 Not Found` - User profile not found

---

**Status:** All upselling endpoints now require authentication
**Breaking Change:** Yes - frontend must update API calls
**Security:** High - no email spoofing possible
**Date:** October 7, 2025
