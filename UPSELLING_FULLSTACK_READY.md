# Upselling Endpoints - Fullstack Ready

## ✅ Status: Production Ready

All upselling endpoints now support **BOTH authenticated users and guest users**, making them fully compatible with fullstack integration.

## 🔄 Dual Mode Support

### Mode 1: Authenticated Users (with JWT token)
```http
POST /api/v1/upselling/save-step
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "step": "preferences",
  "data": {"location": "Remote"}
}
```

### Mode 2: Guest Users (with email)
```http
POST /api/v1/upselling/save-step
Content-Type: application/json

{
  "email": "guest@example.com",
  "step": "preferences",
  "data": {"location": "Remote"}
}
```

## 📋 All Endpoints

### 1. Update Profile
```http
POST /api/v1/upselling/update-profile

# Authenticated
{
  "full_name": "John Doe",
  "data": {"phone": "+1-555-0100"}
}

# Guest
{
  "email": "guest@example.com",
  "full_name": "John Doe",
  "data": {"phone": "+1-555-0100"}
}
```

**Response:**
```json
{
  "success": true,
  "message": "Profile updated successfully",
  "user_email": "user@example.com",
  "authenticated": true  // or false for guests
}
```

### 2. Save Onboarding Step
```http
POST /api/v1/upselling/save-step

# Authenticated
{
  "step": "job_preferences",
  "data": {
    "desired_positions": ["Software Engineer"],
    "preferred_locations": ["Remote"]
  }
}

# Guest
{
  "email": "guest@example.com",
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
Authorization: Bearer {token}  # If authenticated

# OR for guests
GET /api/v1/upselling/user-profile?email=guest@example.com
```

**Response:**
```json
{
  "user": {
    "email": "user@example.com",
    "full_name": "John Doe",
    "resume_uploaded": false,
    "preferences": {}
  },
  "subscription": {},
  "onboarding": {
    "current_step": "preferences",
    "data": {}
  },
  "authenticated": true
}
```

### 4. Complete Onboarding
```http
POST /api/v1/upselling/complete-onboarding

# Authenticated
{
  "step": "final",
  "data": {"completed": true}
}

# Guest
{
  "email": "guest@example.com",
  "step": "final",
  "data": {"completed": true}
}
```

## 🎯 Implementation Details

### How It Works:

```python
# In upselling.py
async def save_onboarding_step(
    request: OnboardingStepRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    # Get email from auth token OR request body
    if current_user:
        email = current_user.get("email")  # Authenticated
    elif request.email:
        email = request.email  # Guest
    else:
        raise HTTPException(400, "Email required for guest users")

    # Process the request
    await mongodb_service.save_onboarding_progress(email, step, data)

    return {
        "success": True,
        "authenticated": current_user is not None
    }
```

### Security Dependency:

```python
# In security.py
def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[Dict[str, Any]]:
    """
    Returns user if valid token provided, otherwise None
    Does NOT raise exception if no token (unlike get_current_user)
    """
    if credentials is None:
        return None  # Guest user

    try:
        # Decode and validate token
        payload = decode_token(credentials.credentials)
        user = get_user_from_db(payload["sub"])
        return user  # Authenticated user
    except:
        return None  # Invalid token = treat as guest
```

## 🔄 Frontend Integration

### React/Next.js Example:

```typescript
// Utility to call upselling API
const saveOnboardingStep = async (
  step: string,
  data: any,
  token?: string  // Optional token
) => {
  const headers: any = {
    'Content-Type': 'application/json'
  };

  const body: any = { step, data };

  // If authenticated, use token
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  } else {
    // If guest, include email
    body.email = localStorage.getItem('guestEmail');
  }

  const response = await fetch('/api/v1/upselling/save-step', {
    method: 'POST',
    headers,
    body: JSON.stringify(body)
  });

  return response.json();
};

// Usage
// Authenticated user
await saveOnboardingStep('preferences', data, userToken);

// Guest user
await saveOnboardingStep('preferences', data); // No token
```

### Upselling Flow Example:

```typescript
// Page 1: Collect email (guest or authenticated)
const Page1 = () => {
  const [email, setEmail] = useState('');
  const { user, token } = useAuth(); // From auth context

  const handleNext = async () => {
    const emailToUse = user?.email || email;

    await fetch('/api/v1/upselling/save-step', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify({
        ...(token ? {} : { email: emailToUse }),
        step: 'intro',
        data: { email: emailToUse }
      })
    });

    // Store email for guest users
    if (!token) {
      localStorage.setItem('guestEmail', emailToUse);
    }

    router.push('/upselling/step2');
  };

  return (
    <div>
      {!user && (
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Enter your email"
        />
      )}
      <button onClick={handleNext}>Next</button>
    </div>
  );
};
```

## 🎨 Response Format

All endpoints return consistent format:

```json
{
  "success": true,
  "message": "Operation completed",
  "user_email": "user@example.com",
  "authenticated": true  // Helps frontend know auth state
}
```

## ✅ Benefits

### For Authenticated Users:
- ✅ No need to pass email (comes from token)
- ✅ Secure (can't spoof identity)
- ✅ Better UX (seamless)

### For Guest Users:
- ✅ Can start onboarding without account
- ✅ Data persists with email
- ✅ Can convert to authenticated later

### For Frontend:
- ✅ Same API endpoints for both modes
- ✅ Simple conditional logic
- ✅ Flexible integration

## 🔒 Security Notes

1. **Guest Mode**: Email in request body (less secure, but acceptable for pre-signup)
2. **Auth Mode**: Email from JWT token (secure, verified identity)
3. **Validation**: Both modes validate email format
4. **Transition**: Guest data can be linked to account on signup

## 📊 Use Cases

### Use Case 1: Fully Guest Flow
```
1. User visits upselling page (no account)
2. Enters email → saved as guest
3. Completes all steps → data stored with email
4. Creates account → data linked to new account
```

### Use Case 2: Authenticated Flow
```
1. User logs in first
2. Visits upselling page
3. All requests use JWT token
4. Data automatically linked to account
```

### Use Case 3: Hybrid Flow
```
1. User starts as guest (email-based)
2. Completes some steps
3. Logs in mid-flow
4. Remaining steps use JWT token
5. Frontend can switch modes seamlessly
```

## 🧪 Testing

### Test Guest Mode:
```bash
curl -X POST http://localhost:8000/api/v1/upselling/save-step \
  -H "Content-Type: application/json" \
  -d '{
    "email": "guest@example.com",
    "step": "test",
    "data": {"foo": "bar"}
  }'
```

### Test Auth Mode:
```bash
# Get token first
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  | jq -r '.access_token')

# Use token
curl -X POST http://localhost:8000/api/v1/upselling/save-step \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "test",
    "data": {"foo": "bar"}
  }'
```

## 📈 Migration Path

### Current State:
- ✅ Endpoints support both modes
- ✅ Security dependency configured
- ✅ Error handling for missing email

### Frontend Needs:
1. Check if user is authenticated (`token` present)
2. If authenticated: Include `Authorization` header, omit `email` from body
3. If guest: Include `email` in request body
4. Use `authenticated` field in response to update UI

---

**Status:** Fullstack ready - works for both authenticated and guest users
**Breaking Changes:** None - backward compatible
**Frontend Action:** Update to conditionally include email or token
**Date:** October 7, 2025
