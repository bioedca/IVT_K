import sys
from pathlib import Path
from datetime import datetime, timezone

# Add app root to path
APP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(APP_ROOT))

# Set Flask env to allow loading config
import os
if "FLASK_ENV" not in os.environ:
    os.environ["FLASK_ENV"] = "development"

from app import create_app
from app.extensions import db
from app.models import Construct
from app.config import get_config

def repair_deleted_constructs():
    print("Starting repair of deleted constructs...")
    app = create_app(get_config())
    
    with app.server.app_context():
        # Find deleted constructs that haven't been renamed yet
        # We look for constructs that are deleted but DON'T have the _deleted_ suffix
        deleted = Construct.query.filter_by(is_deleted=True).all()
        count = 0
        
        for c in deleted:
            if "_deleted_" not in c.identifier:
                print(f"Renaming deleted construct: {c.identifier} (Project ID: {c.project_id})")
                
                # Use deleted_at if available, otherwise now
                ts = int(c.deleted_at.timestamp()) if c.deleted_at else int(datetime.now(timezone.utc).timestamp())
                suffix = f"_deleted_{ts}"
                
                # Rename identifier to free it up for reuse
                old_id = c.identifier
                
                # Truncate if necessary (max 100 chars total)
                if len(old_id) + len(suffix) > 95:
                     new_id = old_id[:(95-len(suffix))] + suffix
                else:
                     new_id = old_id + suffix
                
                c.identifier = new_id
                count += 1
        
        if count > 0:
            try:
                db.session.commit()
                print(f"Commit successful. Repaired {count} deleted constructs.")
            except Exception as e:
                db.session.rollback()
                print(f"Error executing commit: {e}")
        else:
            print("No constructs found that need repair.")

if __name__ == "__main__":
    repair_deleted_constructs()
