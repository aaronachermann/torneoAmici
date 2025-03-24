from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time, timedelta
from itertools import combinations
import os
import random

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


# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/teams', methods=['GET', 'POST'])
def teams():
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        
        # Verifica se esiste già una squadra con lo stesso nome
        if Team.query.filter_by(name=team_name).first():
            flash('Il nome della squadra esiste già')
            return redirect(url_for('teams'))
        
        # Verifica se sono già presenti 16 squadre
        if Team.query.count() >= 16:
            flash('È possibile inserire un massimo di 16 squadre.')
            return redirect(url_for('teams'))
        
        team = Team(name=team_name)
        db.session.add(team)
        db.session.commit()
        
        flash(f'Squadra {team_name} aggiunta con successo')
    
    teams = Team.query.all()
    team_count = Team.query.count()
    max_teams = 16
    return render_template('teams.html', teams=teams, team_count=team_count, max_teams=max_teams)



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

@app.route('/generate_groups', methods=['POST'])
def generate_groups():
    teams = Team.query.all()
    
    if len(teams) != 16:
        flash(f'Servono esattamente 16 squadre per generare i gironi. Attualmente ci sono {len(teams)} squadre.')
        return redirect(url_for('teams'))
    
    # Assign teams to groups A, B, C, D (4 teams per group)
    groups = ['A', 'B', 'C', 'D']
    random.shuffle(teams)
    for i, team in enumerate(teams):
        print(i, team)
        team.group = groups[i // 4]
    
    db.session.commit()
    flash('Le squadre sono state assegnate ai gironi')
    
    return redirect(url_for('groups'))


@app.route('/regenerate_groups', methods=['POST'])
def regenerate_groups():
    teams = Team.query.all()
    
    if len(teams) != 16:
        flash(f'Servono esattamente 16 squadre per rigenerare i gironi. Attualmente ci sono {len(teams)} squadre.')
        return redirect(url_for('groups'))
    
    # Assign teams to groups A, B, C, D (4 teams per group)
    groups = ['A', 'B', 'C', 'D']
    random.shuffle(teams)
    for i, team in enumerate(teams):
        team.group = groups[i // 4]
    
    db.session.commit()
    flash('Le squadre sono state riassegnate ai gironi')
    
    return redirect(url_for('groups'))

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if request.method == 'POST':
        # Reset + genera qualificazioni
        Match.query.delete()
        db.session.commit()
        
        generate_qualification_matches()
        flash('Il calendario delle partite di qualificazione è stato generato')
        return redirect(url_for('schedule'))
    
    # 1) Se tutte le qualificazioni sono finite e i quarti non esistono, creali
    if all_group_matches_completed():
        qf_count = Match.query.filter_by(phase='quarterfinal').count()
        if qf_count == 0:
            generate_quarterfinals()
            flash("Quarti di finale generati!")
        else:
            # Se i quarti esistono, aggiorna i bracket
            update_playoff_brackets()
            flash("I tabelloni dei quarti di finale sono stati aggiornati automaticamente!")
    
    # 2) Se i quarti sono completi e le semifinali non esistono, generale
    if all_quarterfinals_completed('Major League') and all_quarterfinals_completed('Beer League'):
        sf_count = Match.query.filter_by(phase='semifinal').count()
        if sf_count == 0:
            generate_semifinals()
            flash("Semifinali generate!")
        else:
            update_semifinals('Major League')
            update_semifinals('Beer League')
            flash("Tabelloni semifinali aggiornati automaticamente!")
    
    # 3) Se le semifinali sono complete e le finali non esistono, generale
    if all_semifinals_completed('Major League') and all_semifinals_completed('Beer League'):
        f_count = Match.query.filter_by(phase='final').count()
        if f_count == 0:
            generate_finals()
            flash("Finali generate!")
        else:
            update_finals('Major League')
            update_finals('Beer League')
            flash("Tabelloni finali aggiornati automaticamente!")
    
    # Recupera tutti i match
    matches = Match.query.order_by(Match.date, Match.time).all()
    matches_by_date = {}
    for match in matches:
        date_str = match.date.strftime('%Y-%m-%d')
        if date_str not in matches_by_date:
            matches_by_date[date_str] = []
        matches_by_date[date_str].append(match)
    
    return render_template('schedule.html', matches_by_date=matches_by_date)

    
    # In GET: se tutte le qualificazioni sono completate, assicurati che esistano le partite playoff e aggiornale
    if all_group_matches_completed():
        # Verifica se ci sono già partite playoff nel database (fase diversa da "group")
        playoff_matches = Match.query.filter(Match.phase != 'group').all()
        if not playoff_matches:
            # Se non esistono, creale
            generate_playoff_matches()
        else:
            # Se esistono, aggiornale in base alle classifiche
            update_playoff_brackets()
        flash("I tabelloni dei playoff sono stati aggiornati automaticamente!")
    
    # Recupera tutti i match (qualifica e playoff) per la visualizzazione
    matches = Match.query.order_by(Match.date, Match.time).all()
    matches_by_date = {}
    for match in matches:
        date_str = match.date.strftime('%Y-%m-%d')
        if date_str not in matches_by_date:
            matches_by_date[date_str] = []
        matches_by_date[date_str].append(match)
    
    return render_template('schedule.html', matches_by_date=matches_by_date)





def generate_qualification_matches():
    year = datetime.now().year
    # Definiamo le date di qualificazione (Sabato e Domenica)
    qualification_dates = [
        datetime(year, 7, 13).date(),  # Sabato
        datetime(year, 7, 14).date()   # Domenica
    ]
    
    match_times = [
        time(10, 0), time(10, 50), time(11, 40), time(12, 30), time(13, 20),
        time(14, 10), time(15, 0), time(15, 50), time(16, 40), time(17, 30),
        time(18, 20), time(19, 10)
    ]
    
    groups = ['A', 'B', 'C', 'D']
    
    # Recupera le squadre per girone
    teams_by_group = { group: Team.query.filter_by(group=group).all() for group in groups }
    
    # Genera le partite round-robin per ogni girone, poi riordina
    group_matches = {}
    for group, teams in teams_by_group.items():
        # Genera tutte le possibili combinazioni (partite) per il girone
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
        
        # Ordina le rimanenti partite in base all'ordine naturale delle squadre (utilizzando gli indici nella lista originale)
        def match_key(match):
            idx1 = teams.index(match[0])
            idx2 = teams.index(match[1])
            return (idx1, idx2)
        remaining = sorted(tutte_partite, key=match_key)
        
        # Unisci le partite ordinate
        ordered_matches.extend(remaining)
        group_matches[group] = ordered_matches
    
    # Intercala le partite dei gironi:
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
    # Se non tutte le partite di qualifica sono state completate, mostra una preview dei playoff
    print("Generating playoff matches...")
    print(all_group_matches_completed())
    if not all_group_matches_completed():
        preview_schedule = {
            'ML_quarterfinals': [
                {'time': time(19, 30), 'match': '1° gruppo C vs 2° gruppo D'},
                {'time': time(20, 15), 'match': '1° gruppo B vs 2° gruppo C'},
                {'time': time(21, 0),  'match': '1° gruppo D vs 2° gruppo A'},
                {'time': time(21, 45), 'match': '1° gruppo A vs 2° gruppo B'},
            ],
            'BL_quarterfinals': [
                {'time': time(19, 30), 'match': '3° gruppo B vs 4° gruppo C'},
                {'time': time(20, 15), 'match': '3° gruppo D vs 4° gruppo A'},
                {'time': time(21, 0),  'match': '3° gruppo A vs 4° gruppo B'},
                {'time': time(21, 45), 'match': '3° gruppo C vs 4° gruppo D'},
            ],
            'ML_semifinals': [
                {'time': time(19, 30), 'match': 'Perdente partita 27 vs Perdente partita 28'},
                {'time': time(20, 15), 'match': 'Perdente partita 25 vs Perdente partita 26'},
                {'time': time(21, 0),  'match': 'Vincente partita 27 vs Vincente partita 28'},
                {'time': time(21, 45), 'match': 'Vincente partita 25 vs Vincente partita 26'},
            ],
            'BL_semifinals': [
                {'time': time(19, 30), 'match': 'Perdente partita 31 vs Perdente partita 32'},
                {'time': time(20, 15), 'match': 'Perdente partita 29 vs Perdente partita 30'},
                {'time': time(21, 0),  'match': 'Vincente partita 31 vs Vincente partita 32'},
                {'time': time(21, 45), 'match': 'Vincente partita 29 vs Vincente partita 30'},
            ],
            'ML_finals': [
                {'time': time(12, 0), 'match': 'Perdente partita 33 vs Perdente partita 34 (7°/8°)'},
                {'time': time(14, 0), 'match': 'Vincente partita 33 vs Vincente partita 34 (5°/6°)'},
                {'time': time(16, 0), 'match': 'Perdente partita 35 vs Perdente partita 36 (3°/4°)'},
                {'time': time(18, 0), 'match': 'Vincente partita 35 vs Vincente partita 36 (1°/2°)'},
            ],
            'BL_finals': [
                {'time': time(11, 0), 'match': 'Perdente partita 37 vs Perdente partita 38 (7°/8°)'},
                {'time': time(13, 0), 'match': 'Vincente partita 37 vs Vincente partita 38 (5°/6°)'},
                {'time': time(15, 0), 'match': 'Perdente partita 39 vs Perdente partita 40 (3°/4°)'},
                {'time': time(17, 0), 'match': 'Vincente partita 39 vs Vincente partita 40 (1°/2°)'},
            ]
        }
        # Qui si può, ad esempio, loggare o mostrare in interfaccia la preview.
        print("Playoff schedule preview (qualificazioni non completate):")
        for phase, matches in preview_schedule.items():
            print(f"\n{phase}:")
            for m in matches:
                print(f"  {m['time'].strftime('%H:%M')} - {m['match']}")
        # Non vengono effettuate modifiche al database
        return

    # Se tutte le partite di qualifica sono concluse, procede con la generazione dei match playoff nel database
    playoff_dates = {
        'ML_quarterfinals': datetime(2024, 7, 15).date(),  # Lunedì
        'BL_quarterfinals': datetime(2024, 7, 16).date(),  # Martedì
        'ML_semifinals': datetime(2024, 7, 18).date(),     # Giovedì
        'BL_semifinals': datetime(2024, 7, 19).date(),     # Venerdì
        'finals': datetime(2024, 7, 20).date()              # Sabato
    }
    
    quarterfinal_times = [time(19, 30), time(20, 15), time(21, 0), time(21, 45)]
    semifinal_times = [time(19, 30), time(20, 15), time(21, 0), time(21, 45)]
    final_times = {
        'Major League': [time(12, 0), time(14, 0), time(16, 0), time(18, 0)],
        'Beer League': [time(11, 0), time(13, 0), time(15, 0), time(17, 0)]
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
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).order_by(Team.name).all()
        groups[group] = teams
    return render_template('groups.html', groups=groups)

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
    # Crea i match placeholder dei quarti di finale per Major e Beer League
    # con date/orari definiti.  
    # Esempio:
    playoff_dates = {
        'ML_quarterfinals': datetime(2024, 7, 15).date(),  # Lunedì
        'BL_quarterfinals': datetime(2024, 7, 16).date(),  # Martedì
    }
    quarterfinal_times = [time(19, 30), time(20, 15), time(21, 0), time(21, 45)]
    
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
    # Crea i match placeholder delle semifinali, se non esistono
    playoff_dates = {
        'ML_semifinals': datetime(2024, 7, 18).date(),
        'BL_semifinals': datetime(2024, 7, 19).date(),
    }
    semifinal_times = [time(19, 30), time(20, 15), time(21, 0), time(21, 45)]
    
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


def generate_finals():
    # Crea i match placeholder delle finali
    playoff_dates = {
        'finals': datetime(2024, 7, 20).date()
    }
    final_times = {
        'Major League': [time(12, 0), time(14, 0), time(16, 0), time(18, 0)],
        'Beer League': [time(11, 0), time(13, 0), time(15, 0), time(17, 0)]
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

