import sys
import os

# Add your app directory to path
sys.path.insert(0, '/home/sysnode/public_html/sysnode.in')

# Load env from config folder
from dotenv import load_dotenv
load_dotenv('/home/sysnode/public_html/sysnode.in/config/.env')

from app import app as application