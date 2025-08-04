from typing import Optional, Dict, Any
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job
import asyncio
from utils.logging import setup_logger

class Scheduler:
    def __init__(self, app):
        self.scheduler = AsyncIOScheduler()
        self.app = app
        self.logger = setup_logger("scheduler")

    def start(self):
        self.logger.info("Starting scheduler...")
        self.scheduler.start()
        # Schedule default jobs
        self.schedule_daily_stock_analysis()
        self.schedule_weekly_portfolio_analysis()

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
                self.logger.info(f"Successfully loaded schedule {job.id}")
                self.logger.debug(f"Job details: {job}")
                self.logger.info(f"Next run time for {job.id} is {job.next_run_time}")
            else:
                self.logger.error(f"Failed to load schedule {job_id}")
        except Exception as e:
            self.logger.error(f"Exception while adding job {job_id}: {e}")

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
            self.logger.error(f"Error getting job {job_id}: {e}")
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
                self.logger.info(f"Job '{job_id}' (task: {job.name}) modified to run now.")
                return True
            except Exception as e:
                self.logger.error(f"Error modifying job '{job_id}' to run now: {e}", exc_info=True)
                return False
        else:
            self.logger.warning(f"Job '{job_id}' not found. Cannot trigger.")
            return False

    #
    # Jobs
    #
    def schedule_daily_stock_analysis(self, hour: int = 15, minute: int = 0):
        # Schedules analyze_stock to run daily at the specified hour and minute
        self.logger.info(f"Scheduling daily analysis at {hour}:{minute}")
        self.add_job(
            func=self.app.daily_stock_report,
            trigger=CronTrigger(hour=hour, minute=minute),
            job_id="daily_stock_report",
            args=None,
            replace_existing=True
        )

    def schedule_weekly_portfolio_analysis(self, day_of_week: str = 'fri', hour: int = 17, minute: int = 0):
        """
        Schedules analyze_stock to run weekly on the specified day_of_week (e.g., 'mon', 'tue', ...), hour, and minute.
        """
        self.logger.info(f"Scheduling weekly analysis on {day_of_week} at {hour:02d}:{minute:02d}")
        self.add_job(
            func=self.app.portfolio_analysis,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            job_id="weekly_portfolio_analysis",
            args=None,
            replace_existing=True
        )
