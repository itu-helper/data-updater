from datetime import datetime
from rich import print as rprint


class Logger:
    log_level = 3  # 0 = nothing, 1 = only errors, 2 = errors + warnings, 3 = all
    time_stamp_color_code = "#999999"
    
    @staticmethod
    def create_message(message: str, log_type: str, color: str) -> str:
        time_stamp = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
        return f"[{Logger.time_stamp_color_code}][{time_stamp}][{log_type.upper()}][/{Logger.time_stamp_color_code}][{color}] {message}"

    @staticmethod
    def log(message: str, log_type: str, color: str = "white") -> None:
        msg = Logger.create_message(message, log_type, color)
        rprint(msg)

    @staticmethod
    def log_info(message: str) -> None:
        if Logger.log_level < 3:
            return
        
        Logger.log(message, "INFO")

    @staticmethod
    def log_warning(message: str) -> None:
        if Logger.log_level < 2:
            return
    
        Logger.log(message, "WARNING", "yellow")

    @staticmethod
    def log_error(message: str) -> None:
        if Logger.log_level < 1:
            return
        
        Logger.log(message, "ERROR", "red")
