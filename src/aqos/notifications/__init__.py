"""
AQOS notifications.

Storage, preferences, templates and an honest record of delivery. Nothing here
sends an email, a push or anything else off this machine: in-app notifications
are rows this system already owns, and every other channel reports itself
unsupported rather than pretending.
"""

from aqos.notifications.types import (
    AQOS_NOTIFICATION_TYPES_VERSION,
    DELIVERED_STATUSES,
    READ_STATE_TRANSITIONS,
    SUPPORTED_CHANNELS,
    TERMINAL_DELIVERY_STATUSES,
    DeliveryStatus,
    InvalidReadStateTransitionError,
    NotificationCategory,
    NotificationChannel,
    NotificationError,
    NotificationPriority,
    NotificationReadState,
    can_transition_read_state,
    is_supported_channel,
    is_terminal_delivery,
    validate_read_state_transition,
)

from aqos.notifications.templates import (
    AQOS_NOTIFICATION_TEMPLATES_VERSION,
    FORBIDDEN_VARIABLES,
    NOTIFICATION_TEMPLATES,
    PLACEHOLDER_PATTERN,
    NotificationTemplate,
    RenderedNotification,
    TemplateError,
    fill,
    list_template_keys,
    render_template,
    require_template,
)

from aqos.notifications.preferences import (
    AQOS_NOTIFICATION_PREFERENCES_VERSION,
    CHANNEL_DISABLED_REASON,
    CHANNEL_UNSUPPORTED_REASON,
    DEFAULT_ENABLED_CHANNELS,
    ResolvedPreference,
    default_enabled,
    resolve_preference,
)

from aqos.notifications.models import (
    AQOS_NOTIFICATION_MODELS_VERSION,
    MAX_BODY_LENGTH,
    MAX_TITLE_LENGTH,
    Notification,
    NotificationDeliveryAttempt,
    NotificationPreference,
)

from aqos.notifications.repositories import (
    AQOS_NOTIFICATION_REPOSITORIES_VERSION,
    NotificationDeliveryAttemptRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
)

from aqos.notifications.delivery import (
    AQOS_NOTIFICATION_DELIVERY_VERSION,
    EMAIL_UNSUPPORTED_REASON,
    PUSH_UNSUPPORTED_REASON,
    DeliveryBackend,
    DeliveryOutcome,
    InAppDeliveryBackend,
    UnsupportedDeliveryBackend,
    assert_delivery_is_honest,
    build_delivery_backends,
)

from aqos.notifications.service import (
    AQOS_NOTIFICATION_SERVICE_VERSION,
    DEFAULT_CHANNELS,
    NotificationResult,
    NotificationService,
)

__all__ = [
    "AQOS_NOTIFICATION_DELIVERY_VERSION",
    "AQOS_NOTIFICATION_MODELS_VERSION",
    "AQOS_NOTIFICATION_PREFERENCES_VERSION",
    "AQOS_NOTIFICATION_REPOSITORIES_VERSION",
    "AQOS_NOTIFICATION_SERVICE_VERSION",
    "AQOS_NOTIFICATION_TEMPLATES_VERSION",
    "AQOS_NOTIFICATION_TYPES_VERSION",
    "CHANNEL_DISABLED_REASON",
    "CHANNEL_UNSUPPORTED_REASON",
    "DEFAULT_CHANNELS",
    "DEFAULT_ENABLED_CHANNELS",
    "DELIVERED_STATUSES",
    "DeliveryBackend",
    "DeliveryOutcome",
    "DeliveryStatus",
    "EMAIL_UNSUPPORTED_REASON",
    "FORBIDDEN_VARIABLES",
    "InAppDeliveryBackend",
    "InvalidReadStateTransitionError",
    "MAX_BODY_LENGTH",
    "MAX_TITLE_LENGTH",
    "NOTIFICATION_TEMPLATES",
    "Notification",
    "NotificationCategory",
    "NotificationChannel",
    "NotificationDeliveryAttempt",
    "NotificationDeliveryAttemptRepository",
    "NotificationError",
    "NotificationPreference",
    "NotificationPreferenceRepository",
    "NotificationPriority",
    "NotificationReadState",
    "NotificationRepository",
    "NotificationResult",
    "NotificationService",
    "NotificationTemplate",
    "PLACEHOLDER_PATTERN",
    "PUSH_UNSUPPORTED_REASON",
    "READ_STATE_TRANSITIONS",
    "RenderedNotification",
    "ResolvedPreference",
    "SUPPORTED_CHANNELS",
    "TERMINAL_DELIVERY_STATUSES",
    "TemplateError",
    "assert_delivery_is_honest",
    "build_delivery_backends",
    "can_transition_read_state",
    "default_enabled",
    "fill",
    "is_supported_channel",
    "is_terminal_delivery",
    "list_template_keys",
    "render_template",
    "require_template",
    "resolve_preference",
    "validate_read_state_transition",
]

