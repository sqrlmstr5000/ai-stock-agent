from typing import Optional, Dict, Any
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job
import asyncio
from utils.logging import setup_logger
logger = setup_logger("scheduler")

class Scheduler:
    def __init__(self, app):
        self.scheduler = AsyncIOScheduler()
        self.app = app

    def start(self):
        logger.info("Starting scheduler...")
        self.scheduler.start()
        # Schedule default jobs
        self.schedule_daily_stock_analysis()
        self.schedule_weekly_portfolio_analysis()
        self.schedule_daily_price_update()
        self.schedule_sync_stock_splits()

    def add_job(self, func, trigger, job_id, args=None, replace_existing=True):
        """
        Generic method to add a job to the scheduler with logging.
        """
        try:
            job = self.scheduler.add_job(
                func,
                trigger,
                args=args,
                id=job_id,
                replace_existing=replace_existing
            )
            if job:
                logger.info(f"Successfully loaded schedule {job.id}")
                logger.debug(f"Job details: {job}")
                logger.info(f"Next run time for {job.id} is {job.next_run_time}")
            else:
                logger.error(f"Failed to load schedule {job_id}")
        except Exception as e:
            logger.error(f"Exception while adding job {job_id}: {e}")

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by its ID.

        Args:
            job_id (str): ID of the job to get

        Returns:
            Optional[Job]: The job if found, None otherwise
        """
        try:
            return self.scheduler.get_job(job_id)
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None

    def get_all_jobs(self) -> list:
        """
        Get all scheduled jobs.

        Returns:
            list: List of all scheduled jobs
        """
        return self.scheduler.get_jobs()
    
    def trigger_job_now(self, job_id: str) -> bool:
        """
        Triggers a scheduled job to run immediately by modifying its next_run_time.

        Args:
            job_id: The ID of the job to trigger.

        Returns:
            True if the job was found and modified to run now, False otherwise.
        """
        job = self.get_job(job_id) # Uses get_job from the base Schedule class
        if job:
            try:
                self.scheduler.modify_job(job_id, next_run_time=datetime.now(self.scheduler.timezone))
                logger.info(f"Job '{job_id}' (task: {job.name}) modified to run now.")
                return True
            except Exception as e:
                logger.error(f"Error modifying job '{job_id}' to run now: {e}", exc_info=True)
                return False
        else:
            logger.warning(f"Job '{job_id}' not found. Cannot trigger.")
            return False

    #
    # Jobs
    #
    def schedule_sync_stock_splits(self, hour: int = 6, minute: int = 0):
        """
        Schedules sync_stock_splits to run every Saturday at 6:00 AM.
        """
        logger.info(f"Scheduling sync_stock_splits every Saturday at {hour:02d}:{minute:02d}")
        self.add_job(
            func=self.app.sync_stock_splits,
            trigger=CronTrigger(day_of_week='sat', hour=hour, minute=minute),
            job_id="sync_stock_splits",
            args=None,
            replace_existing=True
        )

    def schedule_daily_stock_analysis(self, hour: int = 15, minute: int = 0):
        # Schedules analyze_stock to run Mon-Fri at the specified hour and minute
        logger.info(f"Scheduling daily analysis at {hour}:{minute} (Mon-Fri)")
        self.add_job(
            func=self.app.daily_stock_report,
            trigger=CronTrigger(day_of_week='mon-fri', hour=hour, minute=minute),
            job_id="daily_stock_report",
            args=None,
            replace_existing=True
        )

    def schedule_daily_price_update(self, hour: int = 18, minute: int = 0):
        """
        Schedules get_latest_prices to run Mon-Fri at the specified hour and minute (default 18:00).
        """
        logger.info(f"Scheduling daily price update at {hour:02d}:{minute:02d} (Mon-Fri)")
        self.add_job(
            func=self.app.get_latest_prices,
            trigger=CronTrigger(day_of_week='mon-fri', hour=hour, minute=minute),
            job_id="daily_price_update",
            args=None,
            replace_existing=True
        )

    def schedule_weekly_portfolio_analysis(self, day_of_week: str = 'fri', hour: int = 17, minute: int = 0):
        """
        Schedules analyze_stock to run weekly on the specified day_of_week (e.g., 'mon', 'tue', ...), hour, and minute.
        """
        logger.info(f"Scheduling weekly analysis on {day_of_week} at {hour:02d}:{minute:02d}")
        self.add_job(
            func=self.app.portfolio_analysis_all,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            job_id="weekly_portfolio_analysis",
            args=None,
            replace_existing=True
        )

