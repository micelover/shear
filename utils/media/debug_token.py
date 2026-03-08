import json
from datetime import datetime

with open("token.json", "r") as f:
    token_data = json.load(f)

print("=== TOKEN DEBUG ===")
print(f"Has refresh_token: {'refresh_token' in token_data}")
if 'refresh_token' in token_data:
    print(f"Refresh token (first 10 chars): {token_data['refresh_token'][:10]}...")

print(f"Has access_token: {'token' in token_data}")
if 'expiry' in token_data:
    expiry = datetime.fromisoformat(token_data['expiry'].replace('Z', '+00:00'))
    now = datetime.now().astimezone()
    print(f"Access token expires: {expiry}")
    print(f"Current time: {now}")
    print(f"Expired: {expiry < now}")


# # fix_token_format.py
# import json
# from datetime import datetime, timezone

# # Read current token
# with open("token.json", "r") as f:
#     token_data = json.load(f)

# # Check if expiry needs fixing
# if 'expiry' in token_data:
#     # Parse the expiry and ensure it's ISO format with timezone
#     try:
#         # Try to parse as ISO format
#         expiry = datetime.fromisoformat(token_data['expiry'].replace('Z', '+00:00'))
        
#         # Convert to proper ISO format with timezone
#         token_data['expiry'] = expiry.isoformat()
        
#         print(f"✅ Fixed expiry format: {token_data['expiry']}")
        
#         # Write back
#         with open("token.json", "w") as f:
#             json.dump(token_data, f, indent=2)
            
#     except Exception as e:
#         print(f"Error parsing expiry: {e}")

# print("Token format fixed!")