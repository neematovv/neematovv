from aiogram.fsm.state import State, StatesGroup

class SearchStates(StatesGroup):
    waiting_for_query = State()

class AdminStates(StatesGroup):
    waiting_for_movie_code = State()
    waiting_for_movie_title = State()
    waiting_for_movie_description = State()
    waiting_for_movie_genre = State()
    waiting_for_movie_year = State()
    waiting_for_poster = State()
    waiting_for_movie_category = State()
    waiting_for_delete_code = State()
    waiting_for_broadcast = State()
    waiting_for_episode_movie_code = State()
    waiting_for_episode_number = State()
    waiting_for_episode_video = State()
    waiting_for_admin_search = State()
    waiting_for_edit_field = State()
    waiting_for_edit_value = State()
    waiting_for_poster_movie_code = State()
    waiting_for_poster_upload = State()
    waiting_for_trailer_movie_code = State()
    waiting_for_trailer_url = State()
    waiting_for_ep_del_movie_code = State()
    waiting_for_channel_id = State()
    waiting_for_channel_del_select = State()
