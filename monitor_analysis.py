#!/usr/bin/env python3
"""
Real-time monitoring script for tender analysis progress.
Run this to see live updates of the batch analysis.
"""
import time
import sys
from app.db.database import SessionLocal
from app.modules.analyze.db.schema import TenderAnalysis
from sqlalchemy import func

def clear_screen():
    print("\033[2J\033[H", end="")

def monitor_analysis():
    """Monitor analysis progress in real-time."""
    try:
        while True:
            clear_screen()

            db = SessionLocal()
            try:
                # Get all analyses
                all_analyses = db.query(TenderAnalysis).order_by(
                    TenderAnalysis.analysis_started_at.desc()
                ).all()

                # Count by status
                status_counts = db.query(
                    TenderAnalysis.status,
                    func.count(TenderAnalysis.id)
                ).group_by(TenderAnalysis.status).all()

                print("=" * 120)
                print("TENDER ANALYSIS MONITORING - Live Status")
                print("=" * 120)
                print(f"Total Analyses: {len(all_analyses)}")
                print("\nStatus Breakdown:")
                for status, count in status_counts:
                    print(f"  {status}: {count}")

                print("\n" + "=" * 120)
                print(f"{'Tender ID':15} | {'Status':35} | {'Progress':8} | {'Status Message':50}")
                print("=" * 120)

                for analysis in all_analyses:
                    status_msg = (analysis.status_message or '')[:47]
                    status_str = str(analysis.status)

                    # Color coding
                    if 'completed' in status_str:
                        color = '\033[92m'  # Green
                    elif 'failed' in status_str:
                        color = '\033[91m'  # Red
                    elif 'parsing' in status_str or 'pending' in status_str:
                        color = '\033[93m'  # Yellow
                    else:
                        color = '\033[0m'   # Default

                    print(f"{color}{analysis.tender_id:15} | {status_str:35} | {analysis.progress:6}% | {status_msg}\033[0m")

                print("=" * 120)
                print("Press Ctrl+C to exit | Refreshing every 10 seconds...")

            finally:
                db.close()

            time.sleep(10)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    monitor_analysis()
