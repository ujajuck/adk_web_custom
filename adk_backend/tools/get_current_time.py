import datetime
from zoneinfo import ZoneInfo

def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """
    
    timezone_map = {
        "seoul": "Asia/Seoul",
        "서울": "Asia/Seoul",
        "tokyo": "Asia/Tokyo",
        "도쿄": "Asia/Tokyo",
        "new york": "America/New_York",
        "뉴욕": "America/New_York",
        "london": "Europe/London",
        "런던": "Europe/London",
    }
    
    city_lower = city.lower()
    tz_identifier = timezone_map.get(city_lower)
    
    if not tz_identifier:
        return {
            "status": "error",
            "error_message": (
                f"죄송합니다. {city}의 시간대 정보가 없습니다. "
                f"지원 도시: {', '.join(set(timezone_map.keys()))}"
            ),
        }

    try:
        tz = ZoneInfo(tz_identifier)
        now = datetime.datetime.now(tz)
        report = (
            f'{city}의 현재 시간은 {now.strftime("%Y년 %m월 %d일 %H:%M:%S %Z")}입니다.'
        )
        return {"status": "success", "report": report}
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"시간 조회 중 오류가 발생했습니다: {str(e)}"
        }
