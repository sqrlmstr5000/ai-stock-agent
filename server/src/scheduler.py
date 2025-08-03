from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app import StockAnalysisApp
import asyncio
from utils.logging import setup_logger

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.app = StockAnalysisApp()
        self.logger = setup_logger("scheduler")

    def start(self):
        self.logger.info("Starting scheduler...")
        self.scheduler.start()

    def schedule_daily_analysis(self, symbol: str, hour: int = 0, minute: int = 0):
        # Schedules analyze_stock to run daily at the specified hour and minute
        self.logger.info(f"Scheduling daily analysis for {symbol} at {hour:02d}:{minute:02d}")
        self.scheduler.add_job(
            self.app.analyze_stock,
            CronTrigger(hour=hour, minute=minute),
            args=[symbol],
            id=f"analyze_stock_{symbol}",
            replace_existing=True
        )

    def schedule_weekly_analysis(self, symbol: str, day_of_week: str = 'mon', hour: int = 0, minute: int = 0):
        """
        Schedules analyze_stock to run weekly on the specified day_of_week (e.g., 'mon', 'tue', ...), hour, and minute.
        """
        self.logger.info(f"Scheduling weekly analysis for {symbol} on {day_of_week} at {hour:02d}:{minute:02d}")
        self.scheduler.add_job(
            self.app.analyze_stock,
            CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            args=[symbol],
            id=f"analyze_stock_{symbol}_weekly",
            replace_existing=True
        )

    def schedule_weekly_analysis_for_symbols(self, symbols: list, day_of_week: str = 'mon', hour: int = 0, minute_interval: int = 5):
        """
        Schedules analyze_stock for each symbol weekly, staggered by minute_interval to avoid rate limiting.
        """
        for idx, symbol in enumerate(symbols):
            minute = (idx * minute_interval) % 60
            hour_offset = (idx * minute_interval) // 60
            scheduled_hour = hour + hour_offset
            self.logger.info(
                f"Scheduling weekly analysis for {symbol} on {day_of_week} at {scheduled_hour:02d}:{minute:02d}"
            )
            self.scheduler.add_job(
                self.app.analyze_stock,
                CronTrigger(day_of_week=day_of_week, hour=scheduled_hour, minute=minute),
                args=[symbol],
                id=f"analyze_stock_{symbol}_weekly",
                replace_existing=True
            )
