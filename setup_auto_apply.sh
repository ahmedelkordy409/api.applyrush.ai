#!/bin/bash
# Setup script for Auto-Apply Module
# Run this after pulling the new code

echo "🚀 Setting up Auto-Apply Module for ApplyRush.AI"
echo "=================================================="

# 1. Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install playwright asyncio

# 2. Install Playwright browsers
echo ""
echo "🌐 Installing Playwright browsers (this may take a few minutes)..."
playwright install chromium

# 3. Create screenshot directory
echo ""
echo "📁 Creating screenshot directory..."
mkdir -p /tmp/applyrush_screenshots
chmod 777 /tmp/applyrush_screenshots

# 4. Verify installations
echo ""
echo "✅ Verifying installations..."

python3 -c "
import sys
try:
    from playwright.async_api import async_playwright
    print('✓ Playwright installed successfully')
except ImportError:
    print('✗ Playwright installation failed')
    sys.exit(1)
"

# 5. Display next steps
echo ""
echo "=================================================="
echo "✅ Auto-Apply Module Setup Complete!"
echo "=================================================="
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Configure environment variables in .env:"
echo "   AUTO_APPLY_ENABLED=true"
echo "   EMAIL_FORWARDING_DOMAIN=apply.applyrush.ai"
echo "   PLAYWRIGHT_HEADLESS=true"
echo ""
echo "2. Set up email receiving for apply.applyrush.ai:"
echo "   - Configure DNS MX records"
echo "   - Set up AWS SES or Postfix"
echo "   - Create webhook endpoint"
echo ""
echo "3. Add MongoDB collections:"
echo "   - forwarding_emails"
echo "   - auto_apply_applications"
echo ""
echo "4. Test the module:"
echo "   python3 -m pytest tests/test_auto_apply/"
echo ""
echo "5. Start using auto-apply:"
echo "   See AUTO_APPLY_INTEGRATION_COMPLETE.md for examples"
echo ""
echo "=================================================="
echo "📚 Documentation:"
echo "   - AUTO_APPLY_MODULE_GUIDE.md (Comprehensive guide)"
echo "   - AUTO_APPLY_INTEGRATION_COMPLETE.md (Integration summary)"
echo "=================================================="
