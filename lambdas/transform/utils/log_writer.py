import logging
import os

class Logger:
    def __init__(self, log_file: str = '/tmp/default.log', default_level: str = "INFO"):
        """
        Initialise the Logger instance.

        Args:
            log_file (str): Path to the log file. If None, logs will only be sent to CloudWatch (console).
            default_level (str): The default logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        """
        self.logger = logging.getLogger("AppLogger")
        self.logger.setLevel(logging.DEBUG)  # Capture all levels; handlers will filter appropriately.

        # Formatter for log messages
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Console handler (CloudWatch Logs by default)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, default_level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Optional file handler for `/tmp` directory in Lambda
        if log_file:
            # Ensure the log file path is in `/tmp`, the only writable directory in Lambda
            if not log_file.startswith("/tmp/"):
                log_file = f"/tmp/{os.path.basename(log_file)}"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(getattr(logging, default_level.upper(), logging.INFO))
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log(self, level: str, message: str):
        """
        Log a message at the specified level.

        Args:
            level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            message (str): The message to log.
        """
        level = level.upper()
        if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            self.logger.warning(f"Invalid log level: {level}. Defaulting to INFO.")
            level = "INFO"

        log_method = getattr(self.logger, level.lower())
        log_method(message)

    def info(self, message: str):
        self.log("INFO", message)

    def debug(self, message: str):
        self.log("DEBUG", message)

    def warning(self, message: str):
        self.log("WARNING", message)

    def error(self, message: str):
        self.log("ERROR", message)

    def critical(self, message: str):
        self.log("CRITICAL", message)
