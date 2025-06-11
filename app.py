from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time, timedelta
from itertools import combinations
import os
import random
from datetime import datetime, time, timedelta
import calendar

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tournament.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    group = db.Column(db.String(1))  # A, B, C, or D
    
    players = db.relationship('Player', backref='team', lazy=True)
    
    # Aggiungi overlaps per indicare che questa relazione condivide chiavi con team1 e team2
    matches = db.relationship(
        'Match',
        primaryjoin="or_(Team.id == Match.team1_id, Team.id == Match.team2_id)",
        lazy=True,
        overlaps="team1,team2"
    )
    
    # Tournament stats
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    
    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against
    
    @property
    def games_played(self):
        return self.wins + self.losses + self.draws
    
    @property
    def player_points_total(self):
        return sum(player.registration_points for player in self.players)


class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    is_registered = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(20))  # LNA/LNB, 1a Lega, 2a Lega, Non tesserato
    
    # Player stats
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    penalties = db.Column(db.Integer, default=0)
    
    @property
    def registration_points(self):
        if not self.is_registered:
            return 2  # Non tesserato
        
        points_map = {
            'LNA/LNB': 5,
            '1a Lega': 3,
            '2a Lega': 2
        }
        return points_map.get(self.category, 2)
    
    @property
    def total_points(self):
        return self.goals + self.assists


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    team1_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    team2_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    
    # Aggiungi overlaps="matches" per evitare l’avviso di conflitto con la relazione Team.matches
    team1 = db.relationship('Team', foreign_keys=[team1_id], overlaps="matches")
    team2 = db.relationship('Team', foreign_keys=[team2_id], overlaps="matches")
    
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    
    team1_score = db.Column(db.Integer, default=None)
    team2_score = db.Column(db.Integer, default=None)
    
    phase = db.Column(db.String(20), nullable=False)  # 'group', 'quarterfinal', 'semifinal', 'final'
    league = db.Column(db.String(20))  # 'Major League' or 'Beer League'
    
    @property
    def is_completed(self):
        return self.team1_score is not None and self.team2_score is not None
    
    @property
    def winner(self):
        if not self.is_completed:
            return None
        if self.team1_score > self.team2_score:
            return self.team1
        elif self.team2_score > self.team1_score:
            return self.team2
        return None  # Draw

class MatchDescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    team1_description = db.Column(db.String(100))  # es: "1° gruppo C"
    team2_description = db.Column(db.String(100))  # es: "2° gruppo D"
    match_number = db.Column(db.Integer)  # Numero progressivo della partita
    
    match = db.relationship('Match', backref='description', lazy=True)



def get_team1_display_name(self):
    """Restituisce il nome della squadra 1 o la sua descrizione se non ancora determinata."""
    if self.description and self.description.team1_description and not self.team1:
        return self.description.team1_description
    return self.team1.name if self.team1 else "TBD"

def get_team2_display_name(self):
    """Restituisce il nome della squadra 2 o la sua descrizione se non ancora determinata."""
    if self.description and self.description.team2_description and not self.team2:
        return self.description.team2_description
    return self.team2.name if self.team2 else "TBD"

def get_match_number(self):
    """Restituisce il numero progressivo della partita."""
    return self.description.match_number if self.description else self.id

# Aggiungi questi metodi al modello Match
Match.get_team1_display_name = get_team1_display_name
Match.get_team2_display_name = get_team2_display_name
Match.get_match_number = get_match_number




def get_tournament_dates():
    """
    Calcola le date del torneo per l'anno corrente.
    Il torneo inizia sempre il sabato della seconda settimana di luglio.
    """
    current_year = datetime.now().year
    
    # Trova il primo sabato di luglio
    july_first = datetime(current_year, 7, 1)
    
    # Calcola quanti giorni mancano al primo sabato
    # calendar.SATURDAY = 5 (0=lunedì, 1=martedì, ..., 6=domenica)
    days_until_saturday = (calendar.SATURDAY - july_first.weekday()) % 7
    
    # Se il primo luglio è già sabato, days_until_saturday sarà 0
    # Se il primo luglio è domenica, days_until_saturday sarà 6
    first_saturday = july_first + timedelta(days=days_until_saturday)
    
    # Il torneo inizia il sabato della SECONDA settimana (aggiungi 7 giorni)
    tournament_start = first_saturday + timedelta(days=7)
    
    # Calcola tutte le date del torneo
    dates = {
        'qualification_day1': tournament_start.date(),                    # Sabato (qualificazioni)
        'qualification_day2': (tournament_start + timedelta(days=1)).date(),  # Domenica (qualificazioni)
        'quarterfinals_ml': (tournament_start + timedelta(days=2)).date(),     # Lunedì (quarti ML)
        'quarterfinals_bl': (tournament_start + timedelta(days=3)).date(),     # Martedì (quarti BL)
        'semifinals_ml': (tournament_start + timedelta(days=5)).date(),        # Giovedì (semi ML)
        'semifinals_bl': (tournament_start + timedelta(days=6)).date(),        # Venerdì (semi BL)
        'finals': (tournament_start + timedelta(days=7)).date()               # Sabato (finali)
    }
    
    return dates

def get_tournament_times():
    """
    Restituisce gli orari standardizzati per ogni fase del torneo.
    """
    return {
        'qualification_times': [
            time(10, 0), time(10, 50), time(11, 40), time(12, 30), time(13, 20),
            time(14, 10), time(15, 0), time(15, 50), time(16, 40), time(17, 30),
            time(18, 20), time(19, 10)
        ],
        'playoff_times': [time(19, 30), time(20, 15), time(21, 0), time(21, 45)],
        'final_times_ml': [time(12, 0), time(14, 0), time(16, 0), time(18, 0)],
        'final_times_bl': [time(11, 0), time(13, 0), time(15, 0), time(17, 0)]
    }

def format_tournament_dates():
    """
    Restituisce le date del torneo formattate per la visualizzazione.
    """
    dates = get_tournament_dates()
    formatted = {}
    
    for key, date_obj in dates.items():
        formatted[key] = {
            'date': date_obj,
            'formatted': date_obj.strftime('%d/%m/%Y'),
            'day_name': date_obj.strftime('%A'),
            'day_name_it': {
                'Monday': 'Lunedì',
                'Tuesday': 'Martedì', 
                'Wednesday': 'Mercoledì',
                'Thursday': 'Giovedì',
                'Friday': 'Venerdì',
                'Saturday': 'Sabato',
                'Sunday': 'Domenica'
            }.get(date_obj.strftime('%A'), date_obj.strftime('%A'))
        }
    
    return formatted

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/teams')
def teams():
    teams = Team.query.all()
    team_count = Team.query.count()
    max_teams = 16
    return render_template('teams.html', teams=teams, team_count=team_count, max_teams=max_teams)



@app.route('/add_team', methods=['POST'])
def add_team():
    team_name = request.form.get('team_name')
    group = request.form.get('group')
    
    # Verifica se esiste già una squadra con lo stesso nome
    if Team.query.filter_by(name=team_name).first():
        flash('Il nome della squadra esiste già')
        return redirect(url_for('teams'))
    
    # Verifica se sono già presenti 16 squadre
    if Team.query.count() >= 16:
        flash('È possibile inserire un massimo di 16 squadre.')
        return redirect(url_for('teams'))
    
    # Verifica se il girone selezionato ha già 4 squadre
    if group:
        teams_in_group = Team.query.filter_by(group=group).count()
        if teams_in_group >= 4:
            flash(f'Il Girone {group} ha già raggiunto il limite massimo di 4 squadre.')
            return redirect(url_for('teams'))
    
    # Se il girone non è specificato, lascialo vuoto (None)
    if group == '':
        group = None
    
    team = Team(name=team_name, group=group)
    db.session.add(team)
    db.session.commit()
    
    if group:
        flash(f'Squadra {team_name} aggiunta con successo al Girone {group}')
    else:
        flash(f'Squadra {team_name} aggiunta con successo (girone non assegnato)')
    
    return redirect(url_for('teams'))


@app.route('/team/<int:team_id>/update_group', methods=['POST'])
def update_team_group(team_id):
    team = Team.query.get_or_404(team_id)
    new_group = request.form.get('group')
    
    # Se il nuovo girone è vuoto, impostalo a None
    if new_group == '':
        new_group = None
    
    # Verifica se il nuovo girone ha già 4 squadre (escludendo la squadra corrente)
    if new_group:
        teams_in_group = Team.query.filter_by(group=new_group).filter(Team.id != team_id).count()
        if teams_in_group >= 4:
            flash(f'Il Girone {new_group} ha già raggiunto il limite massimo di 4 squadre.')
            return redirect(url_for('teams'))
    
    old_group = team.group
    team.group = new_group
    db.session.commit()
    
    if old_group and new_group:
        flash(f'Squadra {team.name} spostata dal Girone {old_group} al Girone {new_group}')
    elif new_group:
        flash(f'Squadra {team.name} assegnata al Girone {new_group}')
    elif old_group:
        flash(f'Squadra {team.name} rimossa dal Girone {old_group}')
    else:
        flash(f'Girone della squadra {team.name} aggiornato')
    
    return redirect(url_for('teams'))

@app.route('/team/<int:team_id>/edit', methods=['GET', 'POST'])
def edit_team(team_id):
    team = Team.query.get_or_404(team_id)
    if request.method == 'POST':
        new_name = request.form.get('team_name')
        if Team.query.filter(Team.name == new_name, Team.id != team_id).first():
            flash('Il nome della squadra esiste già')
        else:
            team.name = new_name
            db.session.commit()
            flash('Nome della squadra aggiornato con successo')
        return redirect(url_for('teams'))
    return render_template('edit_team.html', team=team)

@app.route('/team/<int:team_id>/delete', methods=['POST'])
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Delete all players associated with the team
    Player.query.filter_by(team_id=team.id).delete()
    
    # Delete all matches associated with the team
    Match.query.filter((Match.team1_id == team.id) | (Match.team2_id == team.id)).delete()
    
    # Delete the team
    db.session.delete(team)
    db.session.commit()
    
    flash(f'Squadra {team.name} eliminata con successo')
    return redirect(url_for('teams'))

@app.route('/team/<int:team_id>', methods=['GET', 'POST'])
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    
    if request.method == 'POST':
        player_name = request.form.get('player_name')
        is_registered = 'is_registered' in request.form
        category = request.form.get('category') if is_registered else None
        
        player = Player(name=player_name, team=team, is_registered=is_registered, category=category)
        db.session.add(player)
        db.session.commit()
        
        # Check if team exceeds registration points limit
        if team.player_points_total > 20:
            flash('Attenzione: La squadra supera il limite di 20 punti tesseramento!')
        
        flash(f'Giocatore {player_name} aggiunto a {team.name}')
    
    return render_template('team_detail.html', team=team)

@app.route('/player/<int:player_id>/delete', methods=['POST'])
def delete_player(player_id):
    player = Player.query.get_or_404(player_id)
    team_id = player.team_id
    
    db.session.delete(player)
    db.session.commit()
    
    flash(f'Giocatore {player.name} rimosso')
    return redirect(url_for('team_detail', team_id=team_id))


def validate_groups_for_tournament():
    """Verifica che tutti i gironi siano completi prima di generare il calendario"""
    for group in ['A', 'B', 'C', 'D']:
        teams_in_group = Team.query.filter_by(group=group).count()
        if teams_in_group != 4:
            return False, f"Il Girone {group} ha {teams_in_group} squadre invece di 4"
    
    # Verifica che non ci siano squadre non assegnate
    unassigned_teams = Team.query.filter_by(group=None).count()
    if unassigned_teams > 0:
        return False, f"Ci sono {unassigned_teams} squadre non assegnate a nessun girone"
    
    return True, "Tutti i gironi sono completi"

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if request.method == 'POST':
        # Verifica che i gironi siano completi prima di generare il calendario
        is_valid, message = validate_groups_for_tournament()
        if not is_valid:
            flash(f'Impossibile generare il calendario: {message}')
            return redirect(url_for('schedule'))
        
        # Genera l'intero calendario del torneo
        generate_complete_tournament()
        return redirect(url_for('schedule'))
    
    # Aggiorna le descrizioni se necessario
    if all_group_matches_completed():
        update_match_descriptions()
    
    # Recupera tutti i match per la visualizzazione
    matches = Match.query.order_by(Match.date, Match.time).all()
    matches_by_date = {}
    for match in matches:
        date_str = match.date.strftime('%Y-%m-%d')
        if date_str not in matches_by_date:
            matches_by_date[date_str] = []
        matches_by_date[date_str].append(match)
    
    return render_template('schedule.html', matches_by_date=matches_by_date)

def generate_complete_tournament():
    """Genera l'intero calendario del torneo con descrizioni per le partite future."""
    
    # Elimina tutte le partite esistenti
    MatchDescription.query.delete()
    Match.query.delete()
    db.session.commit()
    
    # Genera le qualificazioni
    generate_qualification_matches_with_numbers()
    
    # Genera tutti i playoff con descrizioni
    generate_all_playoff_matches_with_descriptions()
    
    db.session.commit()
    flash('Calendario completo del torneo generato con successo!')


def generate_qualification_matches_with_numbers():
    """Genera partite round-robin per gironi con numerazione progressiva."""
    
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    qualification_dates = [
        tournament_dates['qualification_day1'],  # Sabato
        tournament_dates['qualification_day2']   # Domenica
    ]
    match_times = tournament_times['qualification_times']
    
    groups = ['A', 'B', 'C', 'D']
    
    # Recupera le squadre per girone
    teams_by_group = { group: Team.query.filter_by(group=group).all() for group in groups }
    
    # Genera le partite round-robin per ogni girone
    group_matches = {}
    for group, teams in teams_by_group.items():
        from itertools import combinations
        tutte_partite = list(combinations(teams, 2))
        ordered_matches = []
        
        if len(teams) >= 2:
            first_match = (teams[0], teams[1])
            if first_match in tutte_partite:
                ordered_matches.append(first_match)
                tutte_partite.remove(first_match)
        
        if len(teams) > 2:
            last_match = (teams[-2], teams[-1])
            if last_match in tutte_partite:
                ordered_matches.append(last_match)
                tutte_partite.remove(last_match)
        
        def match_key(match):
            idx1 = teams.index(match[0])
            idx2 = teams.index(match[1])
            return (idx1, idx2)
        remaining = sorted(tutte_partite, key=match_key)
        ordered_matches.extend(remaining)
        group_matches[group] = ordered_matches
    
    # Intercala le partite dei gironi
    interleaved_matches = []
    max_rounds = max(len(matches) for matches in group_matches.values())
    for round_index in range(max_rounds):
        for group in groups:
            if round_index < len(group_matches[group]):
                interleaved_matches.append((group_matches[group][round_index], group))
    
    # Assegna le partite agli orari con numerazione progressiva
    scheduled_matches = []
    total_slots = len(qualification_dates) * len(match_times)
    slot_index = 0
    match_number = 1
    
    for (team1, team2), group in interleaved_matches:
        if slot_index >= total_slots:
            break
        day_index = slot_index // len(match_times)
        time_index = slot_index % len(match_times)
        match_date = qualification_dates[day_index]
        match_time = match_times[time_index]
        scheduled_matches.append((team1, team2, match_date, match_time, group, match_number))
        slot_index += 1
        match_number += 1
    
    # Salva le partite nel database
    for team1, team2, match_date, match_time, group, match_num in scheduled_matches:
        match = Match(
            team1=team1,
            team2=team2,
            date=match_date,
            time=match_time,
            phase='group'
        )
        db.session.add(match)
        db.session.flush()  # Per ottenere l'ID
        
        # Aggiungi la descrizione con il numero
        description = MatchDescription(
            match_id=match.id,
            team1_description=team1.name,
            team2_description=team2.name,
            match_number=match_num
        )
        db.session.add(description)

def generate_all_playoff_matches_with_descriptions():
    """Genera tutte le partite playoff con descrizioni invece dei nomi delle squadre."""
    
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    # Continua la numerazione dalle qualificazioni
    last_match_number = 24  # Assumendo 24 partite di qualificazione
    
    # MAJOR LEAGUE - Quarti di finale (Lunedì)
    ml_quarterfinal_descriptions = [
        ("1° gruppo C", "2° gruppo D"),
        ("1° gruppo B", "2° gruppo C"),
        ("1° gruppo D", "2° gruppo A"),
        ("1° gruppo A", "2° gruppo B")
    ]
    
    ml_quarterfinal_matches = []
    for i, (team1_desc, team2_desc) in enumerate(ml_quarterfinal_descriptions):
        match_number = last_match_number + i + 1
        match_time = tournament_times['playoff_times'][i]
        
        match = Match(
            team1_id=1,  # Placeholder
            team2_id=2,  # Placeholder
            date=tournament_dates['quarterfinals_ml'],
            time=match_time,
            phase='quarterfinal',
            league='Major League'
        )
        db.session.add(match)
        db.session.flush()
        
        description = MatchDescription(
            match_id=match.id,
            team1_description=team1_desc,
            team2_description=team2_desc,
            match_number=match_number
        )
        db.session.add(description)
        ml_quarterfinal_matches.append(match_number)
    
    last_match_number += 4
    
    # BEER LEAGUE - Quarti di finale (Martedì)
    bl_quarterfinal_descriptions = [
        ("3° gruppo B", "4° gruppo C"),
        ("3° gruppo D", "4° gruppo A"),
        ("3° gruppo A", "4° gruppo B"),
        ("3° gruppo C", "4° gruppo D")
    ]
    
    bl_quarterfinal_matches = []
    for i, (team1_desc, team2_desc) in enumerate(bl_quarterfinal_descriptions):
        match_number = last_match_number + i + 1
        match_time = tournament_times['playoff_times'][i]
        
        match = Match(
            team1_id=1,  # Placeholder
            team2_id=2,  # Placeholder
            date=tournament_dates['quarterfinals_bl'],
            time=match_time,
            phase='quarterfinal',
            league='Beer League'
        )
        db.session.add(match)
        db.session.flush()
        
        description = MatchDescription(
            match_id=match.id,
            team1_description=team1_desc,
            team2_description=team2_desc,
            match_number=match_number
        )
        db.session.add(description)
        bl_quarterfinal_matches.append(match_number)
    
    last_match_number += 4
    
    # MAJOR LEAGUE - Semifinali (Giovedì)
    ml_semifinal_descriptions = [
        (f"Perdente partita {ml_quarterfinal_matches[2]}", f"Perdente partita {ml_quarterfinal_matches[3]}"),  # 5°-8°
        (f"Perdente partita {ml_quarterfinal_matches[0]}", f"Perdente partita {ml_quarterfinal_matches[1]}"),  # 5°-8°
        (f"Vincente partita {ml_quarterfinal_matches[2]}", f"Vincente partita {ml_quarterfinal_matches[3]}"),  # 1°-4°
        (f"Vincente partita {ml_quarterfinal_matches[0]}", f"Vincente partita {ml_quarterfinal_matches[1]}")   # 1°-4°
    ]
    
    ml_semifinal_matches = []
    for i, (team1_desc, team2_desc) in enumerate(ml_semifinal_descriptions):
        match_number = last_match_number + i + 1
        match_time = tournament_times['playoff_times'][i]
        
        match = Match(
            team1_id=1,  # Placeholder
            team2_id=2,  # Placeholder
            date=tournament_dates['semifinals_ml'],
            time=match_time,
            phase='semifinal',
            league='Major League'
        )
        db.session.add(match)
        db.session.flush()
        
        description = MatchDescription(
            match_id=match.id,
            team1_description=team1_desc,
            team2_description=team2_desc,
            match_number=match_number
        )
        db.session.add(description)
        ml_semifinal_matches.append(match_number)
    
    last_match_number += 4
    
    # BEER LEAGUE - Semifinali (Venerdì)
    bl_semifinal_descriptions = [
        (f"Perdente partita {bl_quarterfinal_matches[2]}", f"Perdente partita {bl_quarterfinal_matches[3]}"),  # 5°-8°
        (f"Perdente partita {bl_quarterfinal_matches[0]}", f"Perdente partita {bl_quarterfinal_matches[1]}"),  # 5°-8°
        (f"Vincente partita {bl_quarterfinal_matches[2]}", f"Vincente partita {bl_quarterfinal_matches[3]}"),  # 1°-4°
        (f"Vincente partita {bl_quarterfinal_matches[0]}", f"Vincente partita {bl_quarterfinal_matches[1]}")   # 1°-4°
    ]
    
    bl_semifinal_matches = []
    for i, (team1_desc, team2_desc) in enumerate(bl_semifinal_descriptions):
        match_number = last_match_number + i + 1
        match_time = tournament_times['playoff_times'][i]
        
        match = Match(
            team1_id=1,  # Placeholder
            team2_id=2,  # Placeholder
            date=tournament_dates['semifinals_bl'],
            time=match_time,
            phase='semifinal',
            league='Beer League'
        )
        db.session.add(match)
        db.session.flush()
        
        description = MatchDescription(
            match_id=match.id,
            team1_description=team1_desc,
            team2_description=team2_desc,
            match_number=match_number
        )
        db.session.add(description)
        bl_semifinal_matches.append(match_number)
    
    last_match_number += 4
    
    # FINALI (Sabato) - Major League
    ml_final_descriptions = [
        (f"Perdente partita {ml_semifinal_matches[0]}", f"Perdente partita {ml_semifinal_matches[1]}", "7°/8° posto"),
        (f"Vincente partita {ml_semifinal_matches[0]}", f"Vincente partita {ml_semifinal_matches[1]}", "5°/6° posto"),
        (f"Perdente partita {ml_semifinal_matches[2]}", f"Perdente partita {ml_semifinal_matches[3]}", "3°/4° posto"),
        (f"Vincente partita {ml_semifinal_matches[2]}", f"Vincente partita {ml_semifinal_matches[3]}", "1°/2° posto")
    ]
    
    for i, (team1_desc, team2_desc, placement) in enumerate(ml_final_descriptions):
        match_number = last_match_number + i + 1
        match_time = tournament_times['final_times_ml'][i]
        
        match = Match(
            team1_id=1,  # Placeholder
            team2_id=2,  # Placeholder
            date=tournament_dates['finals'],
            time=match_time,
            phase='final',
            league='Major League'
        )
        db.session.add(match)
        db.session.flush()
        
        description = MatchDescription(
            match_id=match.id,
            team1_description=f"{team1_desc} ({placement})",
            team2_description=f"{team2_desc} ({placement})",
            match_number=match_number
        )
        db.session.add(description)
    
    last_match_number += 4
    
    # FINALI (Sabato) - Beer League
    bl_final_descriptions = [
        (f"Perdente partita {bl_semifinal_matches[0]}", f"Perdente partita {bl_semifinal_matches[1]}", "7°/8° posto"),
        (f"Vincente partita {bl_semifinal_matches[0]}", f"Vincente partita {bl_semifinal_matches[1]}", "5°/6° posto"),
        (f"Perdente partita {bl_semifinal_matches[2]}", f"Perdente partita {bl_semifinal_matches[3]}", "3°/4° posto"),
        (f"Vincente partita {bl_semifinal_matches[2]}", f"Vincente partita {bl_semifinal_matches[3]}", "1°/2° posto")
    ]
    
    for i, (team1_desc, team2_desc, placement) in enumerate(bl_final_descriptions):
        match_number = last_match_number + i + 1
        match_time = tournament_times['final_times_bl'][i]
        
        match = Match(
            team1_id=1,  # Placeholder
            team2_id=2,  # Placeholder
            date=tournament_dates['finals'],
            time=match_time,
            phase='final',
            league='Beer League'
        )
        db.session.add(match)
        db.session.flush()
        
        description = MatchDescription(
            match_id=match.id,
            team1_description=f"{team1_desc} ({placement})",
            team2_description=f"{team2_desc} ({placement})",
            match_number=match_number
        )
        db.session.add(description)

def generate_qualification_matches():
    """Genera partite round-robin per gironi con date dinamiche."""
    
    # Ottieni le date e orari dinamici
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    qualification_dates = [
        tournament_dates['qualification_day1'],  # Sabato
        tournament_dates['qualification_day2']   # Domenica
    ]
    match_times = tournament_times['qualification_times']
    
    groups = ['A', 'B', 'C', 'D']
    
    # Recupera le squadre per girone
    teams_by_group = { group: Team.query.filter_by(group=group).all() for group in groups }
    
    # Genera le partite round-robin per ogni girone, poi riordina
    group_matches = {}
    for group, teams in teams_by_group.items():
        # Genera tutte le possibili combinazioni (partite) per il girone
        from itertools import combinations
        tutte_partite = list(combinations(teams, 2))
        ordered_matches = []
        
        # Se il girone ha almeno due squadre, la prima partita sarà tra le prime due
        if len(teams) >= 2:
            first_match = (teams[0], teams[1])
            if first_match in tutte_partite:
                ordered_matches.append(first_match)
                tutte_partite.remove(first_match)
        
        # Se il girone ha più di due squadre, la seconda partita sarà tra le ultime due
        if len(teams) > 2:
            last_match = (teams[-2], teams[-1])
            if last_match in tutte_partite:
                ordered_matches.append(last_match)
                tutte_partite.remove(last_match)
        
        # Ordina le rimanenti partite in base all'ordine naturale delle squadre
        def match_key(match):
            idx1 = teams.index(match[0])
            idx2 = teams.index(match[1])
            return (idx1, idx2)
        remaining = sorted(tutte_partite, key=match_key)
        
        # Unisci le partite ordinate
        ordered_matches.extend(remaining)
        group_matches[group] = ordered_matches
    
    # Intercala le partite dei gironi
    interleaved_matches = []
    max_rounds = max(len(matches) for matches in group_matches.values())
    for round_index in range(max_rounds):
        for group in groups:
            if round_index < len(group_matches[group]):
                interleaved_matches.append((group_matches[group][round_index], group))
    
    # Assegna le partite agli orari disponibili sui due giorni
    scheduled_matches = []
    total_slots = len(qualification_dates) * len(match_times)
    slot_index = 0
    for (team1, team2), group in interleaved_matches:
        if slot_index >= total_slots:
            break  # Se non ci sono più slot disponibili
        day_index = slot_index // len(match_times)
        time_index = slot_index % len(match_times)
        match_date = qualification_dates[day_index]
        match_time = match_times[time_index]
        scheduled_matches.append((team1, team2, match_date, match_time, group))
        slot_index += 1
    
    # Elimina le partite di fase 'group' esistenti e salva quelle nuove nel database
    Match.query.filter_by(phase='group').delete()
    for team1, team2, match_date, match_time, group in scheduled_matches:
        match = Match(
            team1=team1,
            team2=team2,
            date=match_date,
            time=match_time,
            phase='group'
        )
        db.session.add(match)
    
    db.session.commit()

    
def generate_playoff_matches():
    """Genera struttura playoff con date dinamiche."""
    
    # Se non tutte le partite di qualifica sono state completate, mostra una preview dei playoff
    if not all_group_matches_completed():
        # Ottieni le date formattate per la preview
        formatted_dates = format_tournament_dates()
        
        preview_schedule = {
            'ML_quarterfinals': {
                'date': formatted_dates['quarterfinals_ml']['formatted'],
                'day': formatted_dates['quarterfinals_ml']['day_name_it'],
                'matches': [
                    {'time': time(19, 30), 'match': '1° gruppo C vs 2° gruppo D'},
                    {'time': time(20, 15), 'match': '1° gruppo B vs 2° gruppo C'},
                    {'time': time(21, 0), 'match': '1° gruppo D vs 2° gruppo A'},
                    {'time': time(21, 45), 'match': '1° gruppo A vs 2° gruppo B'},
                ]
            },
            'BL_quarterfinals': {
                'date': formatted_dates['quarterfinals_bl']['formatted'],
                'day': formatted_dates['quarterfinals_bl']['day_name_it'],
                'matches': [
                    {'time': time(19, 30), 'match': '3° gruppo B vs 4° gruppo C'},
                    {'time': time(20, 15), 'match': '3° gruppo D vs 4° gruppo A'},
                    {'time': time(21, 0), 'match': '3° gruppo A vs 4° gruppo B'},
                    {'time': time(21, 45), 'match': '3° gruppo C vs 4° gruppo D'},
                ]
            },
            'ML_semifinals': {
                'date': formatted_dates['semifinals_ml']['formatted'],
                'day': formatted_dates['semifinals_ml']['day_name_it'],
                'matches': [
                    {'time': time(19, 30), 'match': 'Perdente partita 27 vs Perdente partita 28'},
                    {'time': time(20, 15), 'match': 'Perdente partita 25 vs Perdente partita 26'},
                    {'time': time(21, 0), 'match': 'Vincente partita 27 vs Vincente partita 28'},
                    {'time': time(21, 45), 'match': 'Vincente partita 25 vs Vincente partita 26'},
                ]
            },
            'BL_semifinals': {
                'date': formatted_dates['semifinals_bl']['formatted'],
                'day': formatted_dates['semifinals_bl']['day_name_it'],
                'matches': [
                    {'time': time(19, 30), 'match': 'Perdente partita 31 vs Perdente partita 32'},
                    {'time': time(20, 15), 'match': 'Perdente partita 29 vs Perdente partita 30'},
                    {'time': time(21, 0), 'match': 'Vincente partita 31 vs Vincente partita 32'},
                    {'time': time(21, 45), 'match': 'Vincente partita 29 vs Vincente partita 30'},
                ]
            },
            'finals': {
                'date': formatted_dates['finals']['formatted'],
                'day': formatted_dates['finals']['day_name_it'],
                'ML_matches': [
                    {'time': time(12, 0), 'match': 'Perdente partita 33 vs Perdente partita 34 (7°/8°)'},
                    {'time': time(14, 0), 'match': 'Vincente partita 33 vs Vincente partita 34 (5°/6°)'},
                    {'time': time(16, 0), 'match': 'Perdente partita 35 vs Perdente partita 36 (3°/4°)'},
                    {'time': time(18, 0), 'match': 'Vincente partita 35 vs Vincente partita 36 (1°/2°)'},
                ],
                'BL_matches': [
                    {'time': time(11, 0), 'match': 'Perdente partita 37 vs Perdente partita 38 (7°/8°)'},
                    {'time': time(13, 0), 'match': 'Vincente partita 37 vs Vincente partita 38 (5°/6°)'},
                    {'time': time(15, 0), 'match': 'Perdente partita 39 vs Perdente partita 40 (3°/4°)'},
                    {'time': time(17, 0), 'match': 'Vincente partita 39 vs Vincente partita 40 (1°/2°)'},
                ]
            }
        }
        
        # Qui si può loggare o mostrare in interfaccia la preview
        print("Playoff schedule preview (qualificazioni non completate):")
        for phase, data in preview_schedule.items():
            if phase != 'finals':
                print(f"\n{phase} - {data['day']} {data['date']}:")
                for m in data['matches']:
                    print(f"  {m['time'].strftime('%H:%M')} - {m['match']}")
            else:
                print(f"\nFinali - {data['day']} {data['date']}:")
                print("  Major League:")
                for m in data['ML_matches']:
                    print(f"    {m['time'].strftime('%H:%M')} - {m['match']}")
                print("  Beer League:")
                for m in data['BL_matches']:
                    print(f"    {m['time'].strftime('%H:%M')} - {m['match']}")
        
        # Non vengono effettuate modifiche al database
        return

    # Se tutte le partite di qualifica sono concluse, procede con la generazione dei match playoff nel database
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    playoff_dates = {
        'ML_quarterfinals': tournament_dates['quarterfinals_ml'],
        'BL_quarterfinals': tournament_dates['quarterfinals_bl'],
        'ML_semifinals': tournament_dates['semifinals_ml'],
        'BL_semifinals': tournament_dates['semifinals_bl'],
        'finals': tournament_dates['finals']
    }
    
    quarterfinal_times = tournament_times['playoff_times']
    semifinal_times = tournament_times['playoff_times']
    final_times = {
        'Major League': tournament_times['final_times_ml'],
        'Beer League': tournament_times['final_times_bl']
    }
    
    # Rimuove eventuali match playoff esistenti (fase diversa da 'group')
    Match.query.filter(Match.phase != 'group').delete()
    
    # Genera i match placeholder per i quarti di finale di Major League
    for match_time in quarterfinal_times:
        match = Match(
            team1_id=1,  # Placeholder, verrà aggiornato in update_playoff_brackets()
            team2_id=2,
            date=playoff_dates['ML_quarterfinals'],
            time=match_time,
            phase='quarterfinal',
            league='Major League'
        )
        db.session.add(match)
    
    # Quarti di finale di Beer League
    for match_time in quarterfinal_times:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['BL_quarterfinals'],
            time=match_time,
            phase='quarterfinal',
            league='Beer League'
        )
        db.session.add(match)
    
    # Semifinali di Major League
    for match_time in semifinal_times:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['ML_semifinals'],
            time=match_time,
            phase='semifinal',
            league='Major League'
        )
        db.session.add(match)
    
    # Semifinali di Beer League
    for match_time in semifinal_times:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['BL_semifinals'],
            time=match_time,
            phase='semifinal',
            league='Beer League'
        )
        db.session.add(match)
    
    # Finali (piazzamento) di Major League
    for match_time in final_times['Major League']:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['finals'],
            time=match_time,
            phase='final',
            league='Major League'
        )
        db.session.add(match)
    
    # Finali (piazzamento) di Beer League
    for match_time in final_times['Beer League']:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['finals'],
            time=match_time,
            phase='final',
            league='Beer League'
        )
        db.session.add(match)
    
    db.session.commit()


@app.route('/tournament_info')
def tournament_info():
    """Route per visualizzare le informazioni sulle date del torneo."""
    formatted_dates = format_tournament_dates()
    tournament_times = get_tournament_times()
    
    return render_template('tournament_info.html', 
                         dates=formatted_dates, 
                         times=tournament_times)

# Aggiungi questo context processor per rendere le date disponibili in tutti i template
@app.context_processor
def inject_tournament_dates():
    """Rende le date del torneo disponibili in tutti i template."""
    try:
        formatted_dates = format_tournament_dates()
        return {'tournament_dates': formatted_dates}
    except:
        return {'tournament_dates': {}}

# Funzione di utilità per ottenere l'anno del torneo
def get_tournament_year():
    """Restituisce l'anno corrente del torneo."""
    return datetime.now().year

# Funzione per verificare se siamo nella stagione del torneo
def is_tournament_season():
    """Verifica se siamo nel periodo del torneo (luglio dell'anno corrente)."""
    now = datetime.now()
    tournament_dates = get_tournament_dates()
    
    # Il torneo è considerato "in stagione" da inizio luglio a fine luglio
    july_start = datetime(now.year, 7, 1).date()
    july_end = datetime(now.year, 7, 31).date()
    
    return july_start <= now.date() <= july_end

# Funzione per calcolare i giorni mancanti al torneo
def days_until_tournament():
    """Calcola quanti giorni mancano all'inizio del torneo."""
    now = datetime.now().date()
    tournament_dates = get_tournament_dates()
    tournament_start = tournament_dates['qualification_day1']
    
    if now <= tournament_start:
        delta = tournament_start - now
        return delta.days
    else:
        # Se il torneo è già passato, calcola per l'anno prossimo
        next_year = datetime.now().year + 1
        july_first_next = datetime(next_year, 7, 1)
        days_until_saturday = (calendar.SATURDAY - july_first_next.weekday()) % 7
        first_saturday_next = july_first_next + timedelta(days=days_until_saturday)
        tournament_start_next = first_saturday_next + timedelta(days=7)
        
        delta = tournament_start_next.date() - now
        return delta.days


@app.route('/match/<int:match_id>', methods=['GET', 'POST'])
def match_detail(match_id):
    match = Match.query.get_or_404(match_id)
    
    if request.method == 'POST':
        team1_score_str = request.form.get('team1_score')
        team2_score_str = request.form.get('team2_score')
        
        if team1_score_str and team2_score_str:
            # Salviamo i vecchi punteggi, se presenti (possono essere None se è la prima volta)
            old_team1_score = match.team1_score
            old_team2_score = match.team2_score
            
            # Aggiorniamo il match con i nuovi punteggi
            match.team1_score = int(team1_score_str)
            match.team2_score = int(team2_score_str)
            
            # Aggiorniamo le statistiche, passando anche i vecchi punteggi
            update_team_stats(match, old_team1_score, old_team2_score)
            
            db.session.commit()
            flash('Risultato della partita registrato')
            
            # Aggiornamento dei tabelloni a seconda della fase (omesso per brevità)
            
            return redirect(url_for('match_detail', match_id=match_id))
    
    team1_players = match.team1.players
    team2_players = match.team2.players
    stats_by_player = {player.id: player for player in (team1_players + team2_players)}
    
    return render_template('match_detail.html', 
                           match=match, 
                           team1_players=team1_players, 
                           team2_players=team2_players, 
                           stats_by_player=stats_by_player)




@app.template_filter('datetime')
def format_datetime(value, format='%d/%m/%Y'):
    return value.strftime(format)

@app.template_filter('timeformat')
def format_time(value, format='%H:%M'):
    return value.strftime(format)


@app.route('/match/<int:match_id>/update_player_stats', methods=['POST'])
def update_player_stats(match_id):
    match = Match.query.get_or_404(match_id)
    
    for player in match.team1.players + match.team2.players:
        player.goals = int(request.form.get(f'player_{player.id}_goals', 0))
        player.assists = int(request.form.get(f'player_{player.id}_assists', 0))
        player.penalties = int(request.form.get(f'player_{player.id}_penalties', 0))
    
    db.session.commit()
    flash('Statistiche dei giocatori aggiornate')
    
    # Update team statistics
    update_team_stats(match)
    
    return redirect(url_for('match_detail', match_id=match_id))


def update_team_stats(match, old_team1_score=None, old_team2_score=None):
    team1 = match.team1
    team2 = match.team2

    # Se esistono vecchi punteggi (ovvero il match aveva già un risultato),
    # sottraiamo quei valori dalle statistiche delle squadre.
    if old_team1_score is not None and old_team2_score is not None:
        team1.goals_for -= old_team1_score
        team1.goals_against -= old_team2_score
        team2.goals_for -= old_team2_score
        team2.goals_against -= old_team1_score

        if old_team1_score > old_team2_score:
            team1.wins -= 1
            team2.losses -= 1
            team1.points -= 3
        elif old_team2_score > old_team1_score:
            team2.wins -= 1
            team1.losses -= 1
            team2.points -= 3
        else:
            team1.draws -= 1
            team2.draws -= 1
            team1.points -= 1
            team2.points -= 1

    # Aggiungiamo i nuovi valori alle statistiche
    team1.goals_for += match.team1_score
    team1.goals_against += match.team2_score
    team2.goals_for += match.team2_score
    team2.goals_against += match.team1_score

    if match.team1_score > match.team2_score:
        team1.wins += 1
        team2.losses += 1
        team1.points += 3
    elif match.team2_score > match.team1_score:
        team2.wins += 1
        team1.losses += 1
        team2.points += 3
    else:
        team1.draws += 1
        team2.draws += 1
        team1.points += 1
        team2.points += 1


def all_group_matches_completed():
    incomplete_matches = Match.query.filter_by(phase='group').filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    return incomplete_matches == 0

def update_playoff_brackets():
    # Get team standings by group
    standings = {}
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).order_by(
            Team.points.desc(), 
            (Team.goals_for - Team.goals_against).desc(),
            Team.goals_for.desc()
        ).all()
        
        standings[group] = teams
    
    # Assign teams to Major League (top 2 from each group)
    major_league_teams = []
    for group in ['A', 'B', 'C', 'D']:
        major_league_teams.extend(standings[group][:2])
    
    # Assign teams to Beer League (bottom 2 from each group)
    beer_league_teams = []
    for group in ['A', 'B', 'C', 'D']:
        beer_league_teams.extend(standings[group][2:])
    
    # Update Major League quarterfinals
    # 1C vs 2D, 1B vs 2C, 1D vs 2A, 1A vs 2B
    major_quarterfinals = Match.query.filter_by(
        phase='quarterfinal', league='Major League'
    ).order_by(Match.time).all()

    # print("Standings Gruppo A:", [(t.name, t.points) for t in standings['A']])
    # print("Standings Gruppo B:", [(t.name, t.points) for t in standings['B']])
    # print("Standings Gruppo C:", [(t.name, t.points) for t in standings['C']])
    # print("Standings Gruppo D:", [(t.name, t.points) for t in standings['D']])

    
    if len(major_quarterfinals) >= 4:
        # QF1
        major_quarterfinals[0].team1_id = standings['C'][0].id
        major_quarterfinals[0].team2_id = standings['D'][1].id
        # QF2
        major_quarterfinals[1].team1_id = standings['B'][0].id
        major_quarterfinals[1].team2_id = standings['C'][1].id
        # QF3
        major_quarterfinals[2].team1_id = standings['D'][0].id
        major_quarterfinals[2].team2_id = standings['A'][1].id
        # QF4
        major_quarterfinals[3].team1_id = standings['A'][0].id
        major_quarterfinals[3].team2_id = standings['B'][1].id
        
    # Update Beer League quarterfinals
    # 3B vs 4C, 3D vs 4A, 3A vs 4B, 3C vs 4D
    beer_quarterfinals = Match.query.filter_by(
        phase='quarterfinal', league='Beer League'
    ).order_by(Match.time).all()
    
    if len(beer_quarterfinals) >= 4:
        beer_quarterfinals[0].team1_id = standings['B'][2].id
        beer_quarterfinals[0].team2_id = standings['C'][3].id
        
        beer_quarterfinals[1].team1_id = standings['D'][2].id
        beer_quarterfinals[1].team2_id = standings['A'][3].id
        
        beer_quarterfinals[2].team1_id = standings['A'][2].id
        beer_quarterfinals[2].team2_id = standings['B'][3].id
        
        beer_quarterfinals[3].team1_id = standings['C'][2].id
        beer_quarterfinals[3].team2_id = standings['D'][3].id
    db.session.commit()

def all_quarterfinals_completed(league):
    incomplete_matches = Match.query.filter_by(
        phase='quarterfinal', league=league
    ).filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    return incomplete_matches == 0

def update_semifinals(league):
    # Get completed quarterfinal matches
    quarterfinals = Match.query.filter_by(
        phase='quarterfinal', league=league
    ).order_by(Match.time).all()
    
    # Get semifinal matches
    semifinals = Match.query.filter_by(
        phase='semifinal', league=league
    ).order_by(Match.time).all()
    
    if len(quarterfinals) >= 4 and len(semifinals) >= 2:
        # Winners of first two quarterfinals go to first semifinal
        semifinals[0].team1_id = quarterfinals[0].winner.id
        semifinals[0].team2_id = quarterfinals[1].winner.id
        
        # Winners of second two quarterfinals go to second semifinal
        semifinals[1].team1_id = quarterfinals[2].winner.id
        semifinals[1].team2_id = quarterfinals[3].winner.id
        
        # Losers go to placement matches
        placement_matches = Match.query.filter_by(
            phase='placement', league=league
        ).order_by(Match.time).all()
        
        if len(placement_matches) >= 2:
            # Losers of first two quarterfinals
            placement_matches[0].team1_id = quarterfinals[0].team1_id if quarterfinals[0].winner.id == quarterfinals[0].team2_id else quarterfinals[0].team2_id
            placement_matches[0].team2_id = quarterfinals[1].team1_id if quarterfinals[1].winner.id == quarterfinals[1].team2_id else quarterfinals[1].team2_id
            
            # Losers of second two quarterfinals
            placement_matches[1].team1_id = quarterfinals[2].team1_id if quarterfinals[2].winner.id == quarterfinals[2].team2_id else quarterfinals[2].team2_id
            placement_matches[1].team2_id = quarterfinals[3].team1_id if quarterfinals[3].winner.id == quarterfinals[3].team2_id else quarterfinals[3].team2_id
    
    db.session.commit()

def all_semifinals_completed(league):
    incomplete_matches = Match.query.filter_by(
        phase='semifinal', league=league
    ).filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    return incomplete_matches == 0

def update_finals(league):
    # Get completed semifinal matches
    semifinals = Match.query.filter_by(
        phase='semifinal', league=league
    ).order_by(Match.time).all()
    
    # Get completed placement matches
    placement_matches = Match.query.filter_by(
        phase='placement', league=league
    ).order_by(Match.time).all()
    
    # Get final matches
    finals = Match.query.filter_by(
        phase='final', league=league
    ).order_by(Match.time).all()
    
    if len(semifinals) >= 2 and len(placement_matches) >= 2 and len(finals) >= 4:
        # 1st-2nd place match (winners of semifinals)
        finals[0].team1_id = semifinals[0].winner.id
        finals[0].team2_id = semifinals[1].winner.id
        
        # 3rd-4th place match (losers of semifinals)
        finals[1].team1_id = semifinals[0].team1_id if semifinals[0].winner.id == semifinals[0].team2_id else semifinals[0].team2_id
        finals[1].team2_id = semifinals[1].team1_id if semifinals[1].winner.id == semifinals[1].team2_id else semifinals[1].team2_id
        
        # 5th-6th place match (winners of placement matches)
        finals[2].team1_id = placement_matches[0].winner.id
        finals[2].team2_id = placement_matches[1].winner.id
        
        # 7th-8th place match (losers of placement matches)
        finals[3].team1_id = placement_matches[0].team1_id if placement_matches[0].winner.id == placement_matches[0].team2_id else placement_matches[0].team2_id
        finals[3].team2_id = placement_matches[1].team1_id if placement_matches[1].winner.id == placement_matches[1].team2_id else placement_matches[1].team2_id
    
    db.session.commit()

@app.route('/standings')
def standings():
    # Group stage standings
    group_standings = {}
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).order_by(
            Team.points.desc(), 
            (Team.goals_for - Team.goals_against).desc(),
            Team.goals_for.desc()
        ).all()
        
        group_standings[group] = teams
    
    # Player statistics
    top_scorers = Player.query.order_by(Player.goals.desc()).limit(10).all()
    top_assists = Player.query.order_by(Player.assists.desc()).limit(10).all()
    most_penalties = Player.query.order_by(Player.penalties.desc()).limit(10).all()
    
    return render_template('standings.html', 
                          group_standings=group_standings,
                          top_scorers=top_scorers,
                          top_assists=top_assists,
                          most_penalties=most_penalties)

@app.route('/init_db')
def init_db():
    db.create_all()
    
    flash('Database inizializzato')
    
    return redirect(url_for('index'))

@app.route('/groups')
def groups():
    groups = {}
    all_teams = Team.query.all()
    
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).order_by(Team.name).all()
        groups[group] = teams
    
    # Calcola statistiche dei gironi
    groups_stats = {
        'complete': sum(1 for group in ['A', 'B', 'C', 'D'] if len(groups[group]) == 4),
        'incomplete': sum(1 for group in ['A', 'B', 'C', 'D'] if 0 < len(groups[group]) < 4),
        'overfull': sum(1 for group in ['A', 'B', 'C', 'D'] if len(groups[group]) > 4),
        'total_teams': len(all_teams)
    }
    
    return render_template('groups.html', groups=groups, all_teams=all_teams, groups_stats=groups_stats)



@app.route('/reset_db', methods=['POST'])
def reset_db():
    if request.form.get('confirm') == 'yes':
        # Drop all tables
        db.drop_all()
        # Recreate all tables
        db.create_all()
        flash('Il database è stato azzerato con successo', 'success')
    else:
        flash('Conferma non ricevuta. Il database non è stato azzerato.', 'warning')
    return redirect(url_for('index'))


@app.route('/reset_schedule', methods=['POST'])
def reset_schedule():
    reset_matches()
    return redirect(url_for('schedule'))

def reset_matches():
    """Elimina tutte le partite e le loro descrizioni."""
    # Elimina le descrizioni delle partite
    MatchDescription.query.delete()
    
    # Elimina tutte le partite
    Match.query.delete()
    
    # Azzerare le statistiche delle squadre
    teams = Team.query.all()
    for team in teams:
        team.wins = 0
        team.losses = 0
        team.draws = 0
        team.goals_for = 0
        team.goals_against = 0
        team.points = 0
    
    db.session.commit()
    flash('Il calendario delle partite e le statistiche delle squadre sono stati azzerati con successo')


def update_match_descriptions():
    """Aggiorna le descrizioni delle partite quando le squadre reali vengono determinate."""
    
    # Aggiorna quarti di finale Major League
    if all_group_matches_completed():
        standings = {}
        for group in ['A', 'B', 'C', 'D']:
            teams = Team.query.filter_by(group=group).order_by(
                Team.points.desc(), 
                (Team.goals_for - Team.goals_against).desc(),
                Team.goals_for.desc()
            ).all()
            standings[group] = teams
        
        # Aggiorna le descrizioni dei quarti di finale ML
        ml_quarterfinals = Match.query.filter_by(
            phase='quarterfinal', league='Major League'
        ).order_by(Match.time).all()
        
        ml_teams = [
            (standings['C'][0], standings['D'][1]),  # 1°C vs 2°D
            (standings['B'][0], standings['C'][1]),  # 1°B vs 2°C  
            (standings['D'][0], standings['A'][1]),  # 1°D vs 2°A
            (standings['A'][0], standings['B'][1])   # 1°A vs 2°B
        ]
        
        for i, (team1, team2) in enumerate(ml_teams):
            if i < len(ml_quarterfinals):
                match = ml_quarterfinals[i]
                match.team1_id = team1.id
                match.team2_id = team2.id
                
                # Aggiorna la descrizione
                if match.description:
                    match.description.team1_description = team1.name
                    match.description.team2_description = team2.name
        
        # Aggiorna le descrizioni dei quarti di finale BL
        bl_quarterfinals = Match.query.filter_by(
            phase='quarterfinal', league='Beer League'
        ).order_by(Match.time).all()
        
        bl_teams = [
            (standings['B'][2], standings['C'][3]),  # 3°B vs 4°C
            (standings['D'][2], standings['A'][3]),  # 3°D vs 4°A
            (standings['A'][2], standings['B'][3]),  # 3°A vs 4°B
            (standings['C'][2], standings['D'][3])   # 3°C vs 4°D
        ]
        
        for i, (team1, team2) in enumerate(bl_teams):
            if i < len(bl_quarterfinals):
                match = bl_quarterfinals[i]
                match.team1_id = team1.id
                match.team2_id = team2.id
                
                # Aggiorna la descrizione
                if match.description:
                    match.description.team1_description = team1.name
                    match.description.team2_description = team2.name
        
        db.session.commit()



@app.route('/insert_random_results', methods=['GET'])
def insert_random_results():
    # Recupera tutte le partite di qualifica
    qualification_matches = Match.query.filter_by(phase='group').all()
    for match in qualification_matches:
        # Se la partita non è completata, assegna punteggi casuali (da 0 a 5 ad esempio)
        if not match.is_completed:
            score1 = random.randint(0, 5)
            score2 = random.randint(0, 5)
            match.team1_score = score1
            match.team2_score = score2
            # Dal momento che è la prima volta, passiamo None come vecchi punteggi
            update_team_stats(match, None, None)
    db.session.commit()
    flash("Risultati casuali inseriti per tutte le partite di qualifica.")

    # Se, dopo aver inserito i risultati, tutte le partite di gruppo sono completate,
    # il sistema (ad esempio nella route match_detail o in schedule)
    # chiamerà update_playoff_brackets() per aggiornare i playoff.
    return redirect(url_for('schedule'))


def generate_quarterfinals():
    """Crea i match placeholder dei quarti di finale con date dinamiche."""
    
    # Ottieni le date e orari dinamici
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    playoff_dates = {
        'ML_quarterfinals': tournament_dates['quarterfinals_ml'],
        'BL_quarterfinals': tournament_dates['quarterfinals_bl'],
    }
    quarterfinal_times = tournament_times['playoff_times']
    
    # Elimina eventuali quarti di finale già esistenti
    Match.query.filter_by(phase='quarterfinal').delete()
    
    # Major League
    for match_time in quarterfinal_times:
        match = Match(
            team1_id=1,  # placeholder
            team2_id=2,  # placeholder
            date=playoff_dates['ML_quarterfinals'],
            time=match_time,
            phase='quarterfinal',
            league='Major League'
        )
        db.session.add(match)
    
    # Beer League
    for match_time in quarterfinal_times:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['BL_quarterfinals'],
            time=match_time,
            phase='quarterfinal',
            league='Beer League'
        )
        db.session.add(match)
    
    db.session.commit()
    # A questo punto puoi chiamare update_playoff_brackets() per assegnare le squadre
    update_playoff_brackets()

def generate_semifinals():
    """Crea i match placeholder delle semifinali con date dinamiche."""
    
    # Ottieni le date e orari dinamici
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    playoff_dates = {
        'ML_semifinals': tournament_dates['semifinals_ml'],
        'BL_semifinals': tournament_dates['semifinals_bl'],
    }
    semifinal_times = tournament_times['playoff_times']
    
    # Elimina eventuali semifinali già esistenti
    Match.query.filter_by(phase='semifinal').delete()
    
    # Major League
    for match_time in semifinal_times:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['ML_semifinals'],
            time=match_time,
            phase='semifinal',
            league='Major League'
        )
        db.session.add(match)
    
    # Beer League
    for match_time in semifinal_times:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['BL_semifinals'],
            time=match_time,
            phase='semifinal',
            league='Beer League'
        )
        db.session.add(match)
    
    db.session.commit()
    # Ora aggiorna le semifinali
    update_semifinals('Major League')
    update_semifinals('Beer League')

# Sostituisci la funzione generate_finals esistente
def generate_finals():
    """Crea i match placeholder delle finali con date dinamiche."""
    
    # Ottieni le date e orari dinamici
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    playoff_dates = {
        'finals': tournament_dates['finals']
    }
    final_times = {
        'Major League': tournament_times['final_times_ml'],
        'Beer League': tournament_times['final_times_bl']
    }
    
    # Elimina eventuali finali già esistenti
    Match.query.filter_by(phase='final').delete()
    
    # Major League
    for match_time in final_times['Major League']:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['finals'],
            time=match_time,
            phase='final',
            league='Major League'
        )
        db.session.add(match)
    
    # Beer League
    for match_time in final_times['Beer League']:
        match = Match(
            team1_id=1,
            team2_id=2,
            date=playoff_dates['finals'],
            time=match_time,
            phase='final',
            league='Beer League'
        )
        db.session.add(match)
    
    db.session.commit()
    # Aggiorna le finali
    update_finals('Major League')
    update_finals('Beer League')

if __name__ == '__main__':
    app.run(debug=True)

