# Channel used for lightweight controller tasks.
CHANNEL_MAIN = 'rest_framework_reactive.main'
# Channel used for CPU-bound observers evaluation.
CHANNEL_WORKER = 'rest_framework_reactive.worker'
# Group used for individual sessions.
GROUP_SESSIONS = 'rest_framework_reactive.session.{session_id}'

# Message type for observer evaluation.
TYPE_EVALUATE = 'observer.evaluate'
# Message type for ORM table change notifications.
TYPE_ORM_NOTIFY = 'observer.orm_notify'
# Message type for polling observable evaluation.
TYPE_POLL = 'observer.poll'
# Message type for observer item updates.
TYPE_ITEM_UPDATE = 'observer.update'

ORM_NOTIFY_KIND_CREATE = 'create'
ORM_NOTIFY_KIND_UPDATE = 'update'
ORM_NOTIFY_KIND_DELETE = 'delete'
