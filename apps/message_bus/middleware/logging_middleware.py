# apps/message_bus/middleware/logging_middleware.py
"""
Logging middleware and configuration for message bus
Provides structured logging with context and observability
"""

import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import contextmanager

import structlog
from pythonjsonlogger import jsonlogger

from config.settings import settings

class MessageBusLogFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for message bus logs"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = datetime.now().isoformat()
        log_record['service'] = 'message_bus'
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        
        # Add environment info
        log_record['environment'] = settings.environment
        
        # Add trace ID if available (for request tracing)
        if hasattr(record, 'trace_id'):
            log_record['trace_id'] = record.trace_id
        
        # Add tenant context if available
        if hasattr(record, 'tenant_id'):
            log_record['tenant_id'] = record.tenant_id
            
        if hasattr(record, 'channel'):
            log_record['channel'] = record.channel

class StructuredLogger:
    """Structured logger with context management"""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        self._context = {}
    
    def with_context(self, **kwargs) -> 'StructuredLogger':
        """Create new logger instance with additional context"""
        new_logger = StructuredLogger(self.logger._context.get('logger', 'message_bus'))
        new_logger._context = {**self._context, **kwargs}
        new_logger.logger = self.logger.bind(**kwargs)
        return new_logger
    
    def info(self, message: str, **kwargs):
        """Log info message with context"""
        self.logger.info(message, **{**self._context, **kwargs})
    
    def error(self, message: str, **kwargs):
        """Log error message with context"""
        self.logger.error(message, **{**self._context, **kwargs})
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self.logger.warning(message, **{**self._context, **kwargs})
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        self.logger.debug(message, **{**self._context, **kwargs})
    
    def exception(self, message: str, **kwargs):
        """Log exception with full traceback"""
        self.logger.exception(message, **{**self._context, **kwargs})

def setup_logging() -> StructuredLogger:
    """Setup logging configuration for message bus"""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.add_logger_name,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.INFO if settings.environment == "production" else logging.DEBUG
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(MessageBusLogFormatter())
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn.access").disabled = True  # Disable uvicorn access logs
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    
    return StructuredLogger("message_bus")

class MessageProcessingLogger:
    """Specialized logger for message processing pipeline"""
    
    def __init__(self, base_logger: StructuredLogger):
        self.base_logger = base_logger
    
    def log_ingress(self, tenant_id: str, channel: str, message_preview: str, 
                   metadata: Optional[Dict[str, Any]] = None):
        """Log incoming message"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            stage="ingress"
        ).info(
            "Message received",
            message_preview=message_preview[:100],  # Limit preview length
            metadata=metadata or {}
        )
    
    def log_normalization_success(self, tenant_id: str, channel: str, 
                                user_id: str, canonical_message_id: str):
        """Log successful message normalization"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            user_id=user_id,
            stage="normalization"
        ).info(
            "Message normalized successfully",
            canonical_message_id=canonical_message_id
        )
    
    def log_normalization_error(self, tenant_id: str, channel: str, 
                              error: str, raw_data: Optional[Dict] = None):
        """Log message normalization error"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            stage="normalization"
        ).error(
            "Message normalization failed",
            error=error,
            raw_data_keys=list(raw_data.keys()) if raw_data else []
        )
    
    def log_rate_limit_hit(self, tenant_id: str, channel: str, 
                          limit_type: str, current_count: int, limit: int):
        """Log rate limit violation"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            stage="rate_limiting"
        ).warning(
            "Rate limit exceeded",
            limit_type=limit_type,
            current_count=current_count,
            limit=limit,
            usage_percentage=round((current_count / limit) * 100, 2)
        )
    
    def log_auth_failure(self, tenant_id: str, channel: str, 
                        reason: str, ip_address: Optional[str] = None):
        """Log authentication failure"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            stage="authentication"
        ).warning(
            "Authentication failed",
            reason=reason,
            ip_address=ip_address
        )
    
    def log_webhook_signature_validation(self, tenant_id: str, channel: str, 
                                       valid: bool, signature_present: bool):
        """Log webhook signature validation"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            stage="webhook_validation"
        ).info(
            "Webhook signature validation",
            valid=valid,
            signature_present=signature_present
        )

class PerformanceLogger:
    """Logger for performance metrics and monitoring"""
    
    def __init__(self, base_logger: StructuredLogger):
        self.base_logger = base_logger
    
    def log_processing_time(self, tenant_id: str, channel: str, 
                          processing_time_ms: float, stage: str = "total"):
        """Log processing time metrics"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            metric_type="performance"
        ).info(
            "Processing time recorded",
            stage=stage,
            processing_time_ms=processing_time_ms,
            processing_time_seconds=processing_time_ms / 1000
        )
    
    def log_throughput(self, channel: str, messages_per_minute: float, 
                      tenant_count: int, period_minutes: int = 1):
        """Log throughput metrics"""
        self.base_logger.with_context(
            channel=channel,
            metric_type="throughput"
        ).info(
            "Throughput metrics",
            messages_per_minute=messages_per_minute,
            tenant_count=tenant_count,
            period_minutes=period_minutes
        )
    
    def log_error_rate(self, channel: str, error_count: int, 
                      total_requests: int, error_rate_percent: float):
        """Log error rate metrics"""
        self.base_logger.with_context(
            channel=channel,
            metric_type="error_rate"
        ).info(
            "Error rate metrics",
            error_count=error_count,
            total_requests=total_requests,
            error_rate_percent=error_rate_percent
        )

class AuditLogger:
    """Audit logger for security and compliance"""
    
    def __init__(self, base_logger: StructuredLogger):
        self.base_logger = base_logger
    
    def log_api_key_validation(self, tenant_id: str, channel: str, 
                             valid: bool, ip_address: Optional[str] = None):
        """Log API key validation events"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            audit_type="api_key_validation"
        ).info(
            "API key validation",
            valid=valid,
            ip_address=ip_address,
            timestamp=datetime.now().isoformat()
        )
    
    def log_tenant_access(self, tenant_id: str, channel: str, 
                         action: str, user_id: Optional[str] = None):
        """Log tenant access events"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            channel=channel,
            audit_type="tenant_access"
        ).info(
            "Tenant access",
            action=action,
            user_id=user_id,
            timestamp=datetime.now().isoformat()
        )
    
    def log_data_processing(self, tenant_id: str, user_id: str, 
                          data_types: list, pii_detected: bool = False):
        """Log data processing for compliance"""
        self.base_logger.with_context(
            tenant_id=tenant_id,
            user_id=user_id,
            audit_type="data_processing"
        ).info(
            "Data processing event",
            data_types=data_types,
            pii_detected=pii_detected,
            timestamp=datetime.now().isoformat()
        )

@contextmanager
def logging_context(**kwargs):
    """Context manager for adding logging context"""
    token = structlog.contextvars.bind_contextvars(**kwargs)
    try:
        yield
    finally:
        structlog.contextvars.reset_contextvars(token)

class LoggingMiddleware:
    """FastAPI middleware for request logging"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.message_logger = MessageProcessingLogger(logger)
        self.performance_logger = PerformanceLogger(logger)
        self.audit_logger = AuditLogger(logger)
    
    async def __call__(self, request, call_next):
        """Process request with logging"""
        start_time = datetime.now()
        
        # Extract context from request
        tenant_id = request.headers.get("x-tenant-id", "unknown")
        channel = self._extract_channel_from_path(request.url.path)
        ip_address = request.client.host if request.client else "unknown"
        
        # Log request start
        with logging_context(
            tenant_id=tenant_id,
            channel=channel,
            ip_address=ip_address,
            request_id=id(request)
        ):
            try:
                response = await call_next(request)
                
                # Calculate processing time
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Log successful request
                self.performance_logger.log_processing_time(
                    tenant_id, channel, processing_time
                )
                
                return response
                
            except Exception as e:
                # Calculate processing time for failed request
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Log error
                self.logger.with_context(
                    tenant_id=tenant_id,
                    channel=channel,
                    processing_time_ms=processing_time
                ).error(
                    "Request processing failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc()
                )
                
                raise
    
    def _extract_channel_from_path(self, path: str) -> str:
        """Extract channel from request path"""
        if "/normalize/" in path:
            parts = path.split("/")
            if len(parts) > 2 and parts[-2] == "normalize":
                return parts[-1]
        return "unknown"

# Global logger instances
logger = setup_logging()
message_logger = MessageProcessingLogger(logger)
performance_logger = PerformanceLogger(logger)
audit_logger = AuditLogger(logger)