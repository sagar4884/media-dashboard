from flask import Blueprint, render_template
from .. import db
from ..models import Movie, Show, TautulliHistory

bp = Blueprint('tautulli', __name__)

@bp.route('/tautulli')
def tautulli_page():
    history = db.session.query(
        TautulliHistory,
        Movie.local_poster_path,
        Movie.overview,
        Show.local_poster_path.label('show_local_poster_path'),
        Show.overview.label('show_overview'),
        Show.title.label('show_title')
    ).outerjoin(Movie, TautulliHistory.title == Movie.title)\
     .outerjoin(Show, TautulliHistory.title.startswith(Show.title))\
     .order_by(TautulliHistory.date.desc())\
     .all()
    return render_template('tautulli.html', history=history)
