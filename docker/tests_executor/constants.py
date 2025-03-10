POINTS_IN_DAY = 24 * 60 // 5  # 288 5-min points
DAYS_IN_WEEK = 7

WORK_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
ACTIONS = [
    'SCALE_UP',
    'SCALE_DOWN',
    'CHANGE_SHAPE',
    'SPLIT',
    'SHUTDOWN',
    'SCHEDULE',
]
WEEKEND_DAYS = ['Saturday', 'Sunday']
WEEK_DAYS = WORK_DAYS + WEEKEND_DAYS

RECOMMENDATION_KEY = 'recommendation'
SCHEDULE_KEY = 'schedule'
RECOMMENDED_SHAPES_KEY = 'recommended_shapes'
START_KEY = 'start'
STOP_KEY = 'stop'
WEEKDAYS_KEY = 'weekdays'
STATS_KEY = 'stats'
STATUS_KEY = 'status'
MESSAGE_KEY = 'message'
ACTIONS_KEY = 'general_actions'
RESOURCE_ID_KEY = 'resource_id'
