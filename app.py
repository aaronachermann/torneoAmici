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
    group_order = db.Column(db.Integer, default=0)  # NUOVO CAMPO per l'ordinamento nel girone
    
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
    def total_goals(self):
        """Totale gol in tutte le partite."""
        return sum(stat.goals for stat in self.match_stats)

    @property  
    def total_assists(self):
        """Totale assist in tutte le partite."""
        return sum(stat.assists for stat in self.match_stats)

    @property
    def total_penalties(self):
        """Totale penalità in tutte le partite."""
        return sum(stat.penalties for stat in self.match_stats)

    @property
    def total_points(self):
        """Totale punti (gol + assist) in tutte le partite."""
        return self.total_goals + self.total_assists

    def get_match_stats(self, match_id):
        """Ottieni le statistiche per una partita specifica."""
        stats = PlayerMatchStats.query.filter_by(
            player_id=self.id, 
            match_id=match_id
        ).first()
        
        if not stats:
            # Crea statistiche vuote se non esistono
            stats = PlayerMatchStats(
                player_id=self.id,
                match_id=match_id,
                goals=0,
                assists=0,
                penalties=0
            )
        
        return stats

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    team1_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)  # NULL per placeholder
    team2_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)  # NULL per placeholder
    
    team1 = db.relationship('Team', foreign_keys=[team1_id], overlaps="matches")
    team2 = db.relationship('Team', foreign_keys=[team2_id], overlaps="matches")
    
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    
    team1_score = db.Column(db.Integer, default=None)
    team2_score = db.Column(db.Integer, default=None)
    
    phase = db.Column(db.String(20), nullable=False)
    league = db.Column(db.String(20))
    
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

    def get_match_number(self):
        """Restituisce il numero progressivo della partita."""
        earlier_matches = Match.query.filter(
            (Match.date < self.date) | 
            ((Match.date == self.date) & (Match.time < self.time))
        ).count()
        return earlier_matches + 1

    def get_team1_display_name(self):
        """Restituisce il nome della squadra 1 o descrizione playoff."""
        # Se la partita è di gruppo e ha team reali, mostra il nome
        if self.phase == 'group' and self.team1:
            return self.team1.name
        
        # Per le partite playoff, usa sempre le descrizioni se team1_id è NULL
        if self.team1_id is None and self.phase != 'group':
            description = self.get_playoff_description()
            return description['team1']
        
        # Se la squadra esiste, mostra il nome reale
        if self.team1:
            return self.team1.name
        
        return "TBD"

    def get_team2_display_name(self):
        """Restituisce il nome della squadra 2 o descrizione playoff."""
        # Se la partita è di gruppo e ha team reali, mostra il nome
        if self.phase == 'group' and self.team2:
            return self.team2.name
        
        # Per le partite playoff, usa sempre le descrizioni se team2_id è NULL
        if self.team2_id is None and self.phase != 'group':
            description = self.get_playoff_description()
            return description['team2']
        
        # Se la squadra esiste, mostra il nome reale
        if self.team2:
            return self.team2.name
        
        return "TBD"

    def get_playoff_description(self):
        """Genera descrizioni per le partite playoff."""
        match_number = self.get_match_number()
        
        if self.phase == 'quarterfinal':
            return self._get_quarterfinal_descriptions(match_number)
        elif self.phase == 'semifinal':
            return self._get_semifinal_descriptions(match_number)
        elif self.phase == 'final':
            return self._get_final_descriptions(match_number)
        
        return {'team1': "TBD", 'team2': "TBD"}


    def _get_quarterfinal_descriptions(self, match_number):
        """Descrizioni per i quarti di finale."""
        if self.league == 'Major League':
            descriptions = {
                25: {'team1': '1° gruppo D', 'team2': '2° gruppo C'},  # ✅ CORRETTO
                26: {'team1': '1° gruppo A', 'team2': '2° gruppo B'},  # ✅ CORRETTO
                27: {'team1': '1° gruppo C', 'team2': '2° gruppo A'},  # ✅ CORRETTO
                28: {'team1': '1° gruppo B', 'team2': '2° gruppo D'}   # ✅ CORRETTO
            }
        else:  # Beer League
            descriptions = {
                29: {'team1': '3° gruppo B', 'team2': '4° gruppo A'},  # ✅ CORRETTO
                30: {'team1': '3° gruppo D', 'team2': '4° gruppo C'},  # ✅ CORRETTO
                31: {'team1': '3° gruppo A', 'team2': '4° gruppo D'},  # ✅ CORRETTO
                32: {'team1': '3° gruppo C', 'team2': '4° gruppo B'}   # ✅ CORRETTO
            }
        
        return descriptions.get(match_number, {'team1': "TBD", 'team2': "TBD"})

    def _get_semifinal_descriptions(self, match_number):
        """Descrizioni per le semifinali."""
        if self.league == 'Major League':
            descriptions = {
                33: {'team1': 'Perdente partita 27', 'team2': 'Perdente partita 28'},
                34: {'team1': 'Perdente partita 25', 'team2': 'Perdente partita 26'},
                35: {'team1': 'Vincente partita 27', 'team2': 'Vincente partita 28'},
                36: {'team1': 'Vincente partita 25', 'team2': 'Vincente partita 26'}
            }
        else:  # Beer League
            descriptions = {
                37: {'team1': 'Perdente partita 31', 'team2': 'Perdente partita 32'},
                38: {'team1': 'Perdente partita 29', 'team2': 'Perdente partita 30'},
                39: {'team1': 'Vincente partita 31', 'team2': 'Vincente partita 32'},
                40: {'team1': 'Vincente partita 29', 'team2': 'Vincente partita 30'}
            }
        
        return descriptions.get(match_number, {'team1': "TBD", 'team2': "TBD"})

    def _get_final_descriptions(self, match_number):
        """Descrizioni per le finali - VERSIONE CORRETTA."""
        if self.league == 'Major League':
            descriptions = {
                42: {'team1': 'Perdente partita 33', 'team2': 'Perdente partita 34'},    # 7°/8° ML
                44: {'team1': 'Vincente partita 33', 'team2': 'Vincente partita 34'},    # 5°/6° ML
                46: {'team1': 'Perdente partita 35', 'team2': 'Perdente partita 36'},    # 3°/4° ML
                48: {'team1': 'Vincente partita 35', 'team2': 'Vincente partita 36'}     # 1°/2° ML
            }
        else:  # Beer League
            # Beer League ha le partite 41, 43, 45, 47 (dispari)
            descriptions = {
                41: {'team1': 'Perdente partita 37', 'team2': 'Perdente partita 38'},    # 7°/8° BL
                43: {'team1': 'Vincente partita 37', 'team2': 'Vincente partita 38'},    # 5°/6° BL
                45: {'team1': 'Perdente partita 39', 'team2': 'Perdente partita 40'},    # 3°/4° BL
                47: {'team1': 'Vincente partita 39', 'team2': 'Vincente partita 40'}     # 1°/2° BL
            }
        
        return descriptions.get(match_number, {'team1': "TBD", 'team2': "TBD"})





def generate_all_playoff_matches_with_null_teams():
    """Genera tutte le partite playoff con team_id NULL invece di placeholder."""
    
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    # MAJOR LEAGUE - Quarti di finale (Lunedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=None,  # NULL invece di placeholder
            team2_id=None,  # NULL invece di placeholder
            date=tournament_dates['quarterfinals_ml'],
            time=match_time,
            phase='quarterfinal',
            league='Major League'
        )
        db.session.add(match)
    
    # BEER LEAGUE - Quarti di finale (Martedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['quarterfinals_bl'],
            time=match_time,
            phase='quarterfinal',
            league='Beer League'
        )
        db.session.add(match)
    
    # MAJOR LEAGUE - Semifinali (Giovedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['semifinals_ml'],
            time=match_time,
            phase='semifinal',
            league='Major League'
        )
        db.session.add(match)
    
    # BEER LEAGUE - Semifinali (Venerdì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['semifinals_bl'],
            time=match_time,
            phase='semifinal',
            league='Beer League'
        )
        db.session.add(match)
    
    # FINALI (Sabato) - Major League
    for i, match_time in enumerate(tournament_times['final_times_ml']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['finals'],
            time=match_time,
            phase='final',
            league='Major League'
        )
        db.session.add(match)
    
    # FINALI (Sabato) - Beer League
    for i, match_time in enumerate(tournament_times['final_times_bl']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['finals'],
            time=match_time,
            phase='final',
            league='Beer League'
        )
        db.session.add(match)




def get_progressive_match_number(match):
    """Calcola il numero progressivo della partita nel torneo."""
    
    # Conta tutte le partite precedenti a questa
    earlier_matches = Match.query.filter(
        (Match.date < match.date) | 
        ((Match.date == match.date) & (Match.time < match.time))
    ).count()
    
    return earlier_matches + 1

def get_quarterfinal_descriptions(match, match_number):
    """Descrizioni per i quarti di finale."""
    
    if match.league == 'Major League':
        # Major League: Partite 25-28
        descriptions = {
            25: {'team1': '1° gruppo C', 'team2': '2° gruppo D'},
            26: {'team1': '1° gruppo B', 'team2': '2° gruppo C'},
            27: {'team1': '1° gruppo D', 'team2': '2° gruppo A'},
            28: {'team1': '1° gruppo A', 'team2': '2° gruppo B'}
        }
    else:  # Beer League
        # Beer League: Partite 29-32
        descriptions = {
            29: {'team1': '3° gruppo B', 'team2': '4° gruppo C'},
            30: {'team1': '3° gruppo D', 'team2': '4° gruppo A'},
            31: {'team1': '3° gruppo A', 'team2': '4° gruppo B'},
            32: {'team1': '3° gruppo C', 'team2': '4° gruppo D'}
        }
    
    return descriptions.get(match_number, {
        'team1': match.team1.name if match.team1 else "TBD",
        'team2': match.team2.name if match.team2 else "TBD"
    })



def get_semifinal_descriptions(match, match_number):
    """Descrizioni per le semifinali."""
    
    if match.league == 'Major League':
        # Major League: Partite 33-36
        descriptions = {
            33: {'team1': 'Perdente partita 27', 'team2': 'Perdente partita 28'},
            34: {'team1': 'Perdente partita 25', 'team2': 'Perdente partita 26'},
            35: {'team1': 'Vincente partita 27', 'team2': 'Vincente partita 28'},
            36: {'team1': 'Vincente partita 25', 'team2': 'Vincente partita 26'}
        }
    else:  # Beer League
        # Beer League: Partite 37-40
        descriptions = {
            37: {'team1': 'Perdente partita 31', 'team2': 'Perdente partita 32'},
            38: {'team1': 'Perdente partita 29', 'team2': 'Perdente partita 30'},
            39: {'team1': 'Vincente partita 31', 'team2': 'Vincente partita 32'},
            40: {'team1': 'Vincente partita 29', 'team2': 'Vincente partita 30'}
        }
    
    return descriptions.get(match_number, {
        'team1': match.team1.name if match.team1 else "TBD",
        'team2': match.team2.name if match.team2 else "TBD"
    })






class MatchDescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    team1_description = db.Column(db.String(100))  # es: "1° gruppo C"
    team2_description = db.Column(db.String(100))  # es: "2° gruppo D"
    match_number = db.Column(db.Integer)  # Numero progressivo della partita
    
    match = db.relationship('Match', backref='description', lazy=True)


class PlayerMatchStats(db.Model):
    """Statistiche di un giocatore in una singola partita."""
    __tablename__ = 'player_match_stats'
    __table_args__ = (
        db.UniqueConstraint('player_id', 'match_id', name='_player_match_uc'),
        {'extend_existing': True}  # Questo risolve l'errore
    )
    
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    penalties = db.Column(db.Integer, default=0)
    
    # Relazioni
    player = db.relationship('Player', backref='match_stats')
    match = db.relationship('Match', backref='player_stats')



#round robin
# def generate_qualification_matches_simple():
#     """Genera partite round-robin per gironi."""
    
#     tournament_dates = get_tournament_dates()
#     tournament_times = get_tournament_times()
    
#     qualification_dates = [
#         tournament_dates['qualification_day1'],  # Sabato
#         tournament_dates['qualification_day2']   # Domenica
#     ]
#     match_times = tournament_times['qualification_times']
    
#     groups = ['A', 'B', 'C', 'D']
    
#     # Recupera le squadre per girone
#     teams_by_group = { group: Team.query.filter_by(group=group).all() for group in groups }
    
#     # Genera le partite round-robin per ogni girone
#     group_matches = {}
#     for group, teams in teams_by_group.items():
#         from itertools import combinations
#         tutte_partite = list(combinations(teams, 2))
#         ordered_matches = []
        
#         if len(teams) >= 2:
#             first_match = (teams[0], teams[1])
#             if first_match in tutte_partite:
#                 ordered_matches.append(first_match)
#                 tutte_partite.remove(first_match)
        
#         if len(teams) > 2:
#             last_match = (teams[-2], teams[-1])
#             if last_match in tutte_partite:
#                 ordered_matches.append(last_match)
#                 tutte_partite.remove(last_match)
        
#         def match_key(match):
#             idx1 = teams.index(match[0])
#             idx2 = teams.index(match[1])
#             return (idx1, idx2)
#         remaining = sorted(tutte_partite, key=match_key)
#         ordered_matches.extend(remaining)
#         group_matches[group] = ordered_matches
    
#     # Intercala le partite dei gironi
#     interleaved_matches = []
#     max_rounds = max(len(matches) for matches in group_matches.values())
#     for round_index in range(max_rounds):
#         for group in groups:
#             if round_index < len(group_matches[group]):
#                 interleaved_matches.append((group_matches[group][round_index], group))
    
#     # Assegna le partite agli orari
#     scheduled_matches = []
#     total_slots = len(qualification_dates) * len(match_times)
#     slot_index = 0
    
#     for (team1, team2), group in interleaved_matches:
#         if slot_index >= total_slots:
#             break
#         day_index = slot_index // len(match_times)
#         time_index = slot_index % len(match_times)
#         match_date = qualification_dates[day_index]
#         match_time = match_times[time_index]
#         scheduled_matches.append((team1, team2, match_date, match_time, group))
#         slot_index += 1
    
#     # Salva le partite nel database
#     for team1, team2, match_date, match_time, group in scheduled_matches:
#         match = Match(
#             team1=team1,
#             team2=team2,
#             date=match_date,
#             time=match_time,
#             phase='group'
#         )
#         db.session.add(match)

def generate_qualification_matches_simple():
    """Genera partite di qualificazione seguendo la logica esatta del torneo reale."""
    
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    qualification_dates = [
        tournament_dates['qualification_day1'],  # Sabato
        tournament_dates['qualification_day2']   # Domenica
    ]
    match_times = tournament_times['qualification_times']
    
    # Sequenza ESATTA delle partite basata sulle immagini del torneo
    QUALIFICATION_SEQUENCE = [
        # SABATO - Partite 1-12
        ('A1', 'A3'),  # Partita 1: 10:00 - Barrhock vs Yellowstone Team
        ('B1', 'B3'),  # Partita 2: 10:50 - Original Twins vs Arosio Capital  
        ('C1', 'C3'),  # Partita 3: 11:40 - Peppa Beer vs Tirabüscion
        ('D1', 'D3'),  # Partita 4: 12:30 - Drunk Junior vs Tre Sejdlar
        ('A3', 'A4'),  # Partita 5: 13:20 - Flory Motos vs Hocktail
        ('B3', 'B4'),  # Partita 6: 14:10 - I Gamb Rott vs Animal's team
        ('C3', 'C4'),  # Partita 7: 15:00 - Bardolino vs Le Padelle
        ('D3', 'D4'),  # Partita 8: 15:50 - HC Caterpillars vs Giügaduu dala Lippa
        ('A1', 'A2'),  # Partita 9: 16:40 - Barrhock vs Flory Motos
        ('B1', 'B2'),  # Partita 10: 17:30 - Original Twins vs I Gamb Rott
        ('C4', 'C1'),  # Partita 11: 18:20 - Peppa Beer vs Bardolino
        ('D1', 'D2'),  # Partita 12: 19:10 - Drunk Junior vs HC Caterpillars
        
        # DOMENICA - Partite 13-24
        ('C2', 'C4'),  # Partita 13: 10:00 - Barrhock vs Hocktail
        ('D2', 'D4'),  # Partita 14: 10:50 - Original Twins vs Animal's team
        ('A2', 'A4'),  # Partita 15: 11:40 - Peppa Beer vs Le Padelle
        ('B2', 'B4'),  # Partita 16: 12:30 - Drunk Junior vs Giügaduu dala Lippa
        ('C3', 'C2'),  # Partita 17: 13:20 - Yellowstone Team vs Flory Motos
        ('D3', 'D2'),  # Partita 18: 14:10 - Arosio Capital vs I Gamb Rott
        ('A3', 'A2'),  # Partita 19: 15:00 - Tirabüscion vs Bardolino
        ('B3', 'B2'),  # Partita 20: 15:50 - Tre Sejdlar vs HC Caterpillars
        ('C1', 'C2'),  # Partita 21: 16:40 - Yellowstone Team vs Hocktail
        ('D4', 'D1'),  # Partita 22: 17:30 - Arosio Capital vs Animal's team
        ('A4', 'A1'),  # Partita 23: 18:20 - Tirabüscion vs Le Padelle
        ('B4', 'B1'),  # Partita 24: 19:10 - Tre Sejdlar vs Giügaduu dala Lippa
    ]
    
    # Recupera le squadre ordinate per girone e posizione
    teams_by_position = {}
    for group in ['A', 'B', 'C', 'D']:
        # Ordina le squadre per group_order (posizione nel girone)
        teams = Team.query.filter_by(group=group).order_by(Team.group_order, Team.name).all()
        
        if len(teams) != 4:
            print(f"ERRORE: Girone {group} ha {len(teams)} squadre invece di 4!")
            return False
        
        # Mappa le posizioni (1=primo, 2=secondo, 3=terzo, 4=quarto)
        for i, team in enumerate(teams):
            position_key = f"{group}{i+1}"  # A1, A2, A3, A4, ecc.
            teams_by_position[position_key] = team
            print(f"Posizione {position_key}: {team.name}")
    
    # Elimina le partite di qualificazione esistenti
    Match.query.filter_by(phase='group').delete()
    
    # Genera le partite seguendo la sequenza esatta
    for i, (pos1, pos2) in enumerate(QUALIFICATION_SEQUENCE):
        # Calcola data e orario
        day_index = i // 12  # 0 per sabato (partite 0-11), 1 per domenica (partite 12-23)
        time_index = i % 12  # Indice dell'orario nel giorno
        
        match_date = qualification_dates[day_index]
        match_time = match_times[time_index]
        
        # Ottieni le squadre dalle posizioni
        team1 = teams_by_position.get(pos1)
        team2 = teams_by_position.get(pos2)
        
        if not team1 or not team2:
            print(f"ERRORE: Non trovate squadre per posizioni {pos1} vs {pos2}")
            continue
        
        # Crea la partita
        match = Match(
            team1=team1,
            team2=team2,
            date=match_date,
            time=match_time,
            phase='group'
        )
        db.session.add(match)
        
        print(f"Partita {i+1}: {team1.name} vs {team2.name} - {match_date} {match_time}")
    
    db.session.commit()
    print("Qualificazioni generate con successo seguendo la logica del torneo!")
    return True


# 3. MODIFICA la funzione generate_all_playoff_matches_simple per usare ID placeholder diversi
def generate_all_playoff_matches_simple():
    """Genera tutte le partite playoff con team_id NULL."""
    
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    # MAJOR LEAGUE - Quarti di finale (Lunedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=None,  # NULL invece di ID fittizio
            team2_id=None,  # NULL invece di ID fittizio
            date=tournament_dates['quarterfinals_ml'],
            time=match_time,
            phase='quarterfinal',
            league='Major League'
        )
        db.session.add(match)
    
    # BEER LEAGUE - Quarti di finale (Martedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['quarterfinals_bl'],
            time=match_time,
            phase='quarterfinal',
            league='Beer League'
        )
        db.session.add(match)
    
    # MAJOR LEAGUE - Semifinali (Giovedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['semifinals_ml'],
            time=match_time,
            phase='semifinal',
            league='Major League'
        )
        db.session.add(match)
    
    # BEER LEAGUE - Semifinali (Venerdì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['semifinals_bl'],
            time=match_time,
            phase='semifinal',
            league='Beer League'
        )
        db.session.add(match)
    
    # FINALI (Sabato) - Major League
    for i, match_time in enumerate(tournament_times['final_times_ml']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['finals'],
            time=match_time,
            phase='final',
            league='Major League'
        )
        db.session.add(match)
    
    # FINALI (Sabato) - Beer League
    for i, match_time in enumerate(tournament_times['final_times_bl']):
        match = Match(
            team1_id=None,
            team2_id=None,
            date=tournament_dates['finals'],
            time=match_time,
            phase='final',
            league='Beer League'
        )
        db.session.add(match)





@app.route('/update_playoffs', methods=['POST'])
def update_playoffs():
    """Aggiorna manualmente i tabelloni playoff quando le qualificazioni sono complete."""
    if all_group_matches_completed():
        update_playoff_brackets()
        flash('Tabelloni playoff aggiornati con le squadre qualificate!')
    else:
        flash('Le qualificazioni devono essere completate prima di aggiornare i playoff.')
    
    return redirect(url_for('schedule'))


def all_phase_matches_completed(phase, league=None):
    """Verifica se tutte le partite di una fase sono completate per una lega specifica."""
    query = Match.query.filter_by(phase=phase)
    if league:
        query = query.filter_by(league=league)
    
    # Conta partite incomplete (con team reali, non NULL)
    incomplete_matches = query.filter(
        Match.team1_id.isnot(None),  # Solo partite con squadre reali
        Match.team2_id.isnot(None),
        (Match.team1_score.is_(None) | Match.team2_score.is_(None))
    ).count()
    
    return incomplete_matches == 0



@app.route('/update_semifinals', methods=['POST'])
def update_semifinals_route():
    """Aggiorna le semifinali quando i quarti sono completati."""
    ml_complete = all_phase_matches_completed('quarterfinal', 'Major League')
    bl_complete = all_phase_matches_completed('quarterfinal', 'Beer League')
    
    if ml_complete and bl_complete:
        update_semifinals('Major League')
        update_semifinals('Beer League')
        flash('Semifinali aggiornate con i vincitori e perdenti dei quarti!')
    else:
        flash('I quarti di finale devono essere completati prima di aggiornare le semifinali.')
    
    return redirect(url_for('schedule'))

@app.route('/debug_playoff_teams_current')
def debug_playoff_teams_current():
    """Debug: mostra i team attuali dei playoff."""
    
    quarterfinals = Match.query.filter_by(phase='quarterfinal').order_by(Match.league, Match.time).all()
    
    info = []
    for match in quarterfinals:
        info.append({
            'match_number': match.get_match_number(),
            'league': match.league,
            'team1': match.team1.name if match.team1 else 'NULL',
            'team2': match.team2.name if match.team2 else 'NULL',
            'expected': match.get_playoff_description()
        })
    
    print(f'Debug quarti attuali: {info}', 'info')
    return redirect(url_for('schedule'))


@app.route('/update_finals', methods=['POST'])
def update_finals_route():
    """Aggiorna le finali quando le semifinali sono completate."""
    ml_complete = all_phase_matches_completed('semifinal', 'Major League')
    bl_complete = all_phase_matches_completed('semifinal', 'Beer League')
    
    if ml_complete and bl_complete:
        update_finals('Major League')
        update_finals('Beer League')
        flash('Finali aggiornate con i vincitori e perdenti delle semifinali!')
    else:
        flash('Le semifinali devono essere completate prima di aggiornare le finali.')
    
    return redirect(url_for('schedule'))


def generate_complete_tournament_simple():
    """Genera l'intero calendario del torneo."""
    
    # Elimina tutte le partite esistenti
    Match.query.delete()
    db.session.commit()
    

    # Genera le qualificazioni
    generate_qualification_matches_simple()
    
    # Genera i playoff
    generate_all_playoff_matches_simple()
    
    db.session.commit()
    print('Calendario completo del torneo generato!')

# Aggiungi questa nuova route per generare il calendario corretto
@app.route('/generate_complete_tournament_fixed', methods=['POST'])
def generate_complete_tournament_fixed():
    """Genera calendario completo con sistema playoff corretto."""
    try:
        generate_complete_tournament_simple()
        return redirect(url_for('schedule'))
    except Exception as e:
        flash(f'Errore durante la generazione: {str(e)}', 'danger')
        return redirect(url_for('schedule'))


@app.route('/debug_finals_mapping')
def debug_finals_mapping():
    """Debug: controlla la mappatura delle finali Beer League."""
    
    # Trova le finali Beer League
    bl_finals = Match.query.filter_by(
        phase='final', 
        league='Beer League'
    ).order_by(Match.time).all()
    
    debug_info = []
    
    for match in bl_finals:
        match_number = match.get_match_number()
        description = match.get_playoff_description()
        
        debug_info.append({
            'match_number': match_number,
            'time': match.time.strftime('%H:%M'),
            'team1_id': match.team1_id,
            'team2_id': match.team2_id,
            'expected_team1': description['team1'],
            'expected_team2': description['team2'],
            'actual_display_team1': match.get_team1_display_name(),
            'actual_display_team2': match.get_team2_display_name()
        })
    
    flash(f'Debug Beer League Finals: {debug_info}', 'info')
    return redirect(url_for('schedule'))



# 4. AGGIUNGI questa route per applicare il fix
@app.route('/fix_playoff_descriptions', methods=['POST'])
def fix_playoff_descriptions():
    """Applica il fix per le descrizioni dei playoff."""
    try:

        # Aggiorna tutti i playoff per usare ID placeholder fittizi
        playoff_matches = Match.query.filter(Match.phase != 'group').all()
        
        for match in playoff_matches:
            # Se la partita usa gli ID placeholder originali (1 e 2), aggiornali
            if match.team1_id in [1, 2] and match.team2_id in [1, 2]:
                match.team1_id = 999  # ID fittizio
                match.team2_id = 998  # ID fittizio
        
        db.session.commit()
        flash('Fix applicato con successo! Le descrizioni dei playoff ora funzionano correttamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante il fix: {str(e)}', 'danger')
    
    return redirect(url_for('schedule'))



# Aggiorna la funzione reset_matches per non toccare MatchDescription
def reset_matches():
    """Elimina tutte le partite."""
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


# 5. ROUTE per il fix completo
@app.route('/fix_complete_playoff_system', methods=['POST'])
def fix_complete_playoff_system():
    """Fix completo del sistema playoff."""
    try:
        # Elimina playoff esistenti
        Match.query.filter(Match.phase != 'group').delete()
        
        # Rigenera i playoff con NULL
        generate_all_playoff_matches_simple()
        
        db.session.commit()
        flash('🎯 Sistema playoff completamente riparato! Ora vedrai le descrizioni corrette.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante il fix: {str(e)}', 'danger')
    
    return redirect(url_for('schedule'))


@app.route('/debug_semifinal_numbers')
def debug_semifinal_numbers():
    """Debug: controlla i numeri delle semifinali Beer League."""
    
    bl_semifinals = Match.query.filter_by(
        phase='semifinal', 
        league='Beer League'
    ).order_by(Match.time).all()
    
    debug_info = []
    for match in bl_semifinals:
        debug_info.append({
            'match_number': match.get_match_number(),
            'time': match.time.strftime('%H:%M'),
            'description': f"{match.get_team1_display_name()} vs {match.get_team2_display_name()}"
        })
    
    flash(f'Semifinali Beer League: {debug_info}', 'info')
    return redirect(url_for('schedule'))


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
            time(10, 0), time(10, 45), time(11, 30), time(12, 15), time(13, 00),
            time(13, 45), time(14, 30), time(15, 15), time(16, 00), time(16, 45),
            time(17, 30), time(18, 15)
        ],
        'playoff_times': [time(19, 00), time(19, 45), time(20, 30), time(21, 15)],
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



# Aggiungi questa route di debug in app.py
@app.route('/debug_playoff_teams')
def debug_playoff_teams():
    playoff_matches = Match.query.filter(Match.phase != 'group').order_by(Match.date, Match.time).all()
    info = []
    
    for match in playoff_matches:
        info.append({
            'match_number': match.get_match_number(),
            'phase': match.phase,
            'league': match.league,
            'team1_id': match.team1_id,
            'team2_id': match.team2_id,
            'expected_team1': match.get_playoff_description()['team1'],
            'expected_team2': match.get_playoff_description()['team2']
        })
    
    flash(f'Debug playoff teams: {info[:10]}', 'info')  # Solo prime 10
    return redirect(url_for('schedule'))


@app.route('/reset_playoff_teams_to_null', methods=['POST'])
def reset_playoff_teams_to_null():
    """Reset dei team_id dei playoff a NULL per mostrare le descrizioni."""
    try:
        playoff_matches = Match.query.filter(Match.phase != 'group').all()
        
        for match in playoff_matches:
            match.team1_id = None
            match.team2_id = None
        
        db.session.commit()
        flash('Team ID dei playoff resettati a NULL. Ora dovresti vedere le descrizioni corrette!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante il reset: {str(e)}', 'danger')
    
    return redirect(url_for('schedule'))



@app.route('/teams')
def teams():
    # Ordina le squadre per girone e poi per group_order
    teams = Team.query.order_by(Team.group.nulls_last(), Team.group_order, Team.name).all()
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
        group_order = 0
    else:
        # Trova il prossimo numero d'ordine per il girone
        max_order = db.session.query(db.func.max(Team.group_order)).filter_by(group=group).scalar()
        group_order = (max_order or 0) + 1
    
    team = Team(name=team_name, group=group, group_order=group_order)
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
    
    # Aggiorna l'ordinamento
    if new_group:
        # Trova il prossimo numero d'ordine per il nuovo girone
        max_order = db.session.query(db.func.max(Team.group_order)).filter_by(group=new_group).scalar()
        team.group_order = (max_order or 0) + 1
    else:
        team.group_order = 0
    
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

# def generate_complete_tournament_with_descriptions():
#     """Genera l'intero calendario del torneo con descrizioni corrette."""
    
#     # Elimina tutte le partite esistenti
#     Match.query.delete()
#     db.session.commit()
    
#     # Genera le qualificazioni
#     generate_qualification_matches_simple()
    
#     # Genera tutti i playoff con placeholder, le descrizioni verranno mostrate automaticamente
#     generate_all_playoff_matches_with_placeholder()
    
#     db.session.commit()
#     flash('Calendario completo del torneo generato con descrizioni!')

def generate_all_playoff_matches_with_placeholder():
    """Genera tutte le partite playoff con placeholder minimi."""
    
    tournament_dates = get_tournament_dates()
    tournament_times = get_tournament_times()
    
    # Usa la prima squadra come placeholder (tanto le descrizioni sono gestite dai metodi)
    first_team = Team.query.first()
    if not first_team:
        flash('Errore: Nessuna squadra trovata', 'danger')
        return
    
    placeholder_id = first_team.id
    
    # MAJOR LEAGUE - Quarti di finale (Lunedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=placeholder_id,
            team2_id=placeholder_id,
            date=tournament_dates['quarterfinals_ml'],
            time=match_time,
            phase='quarterfinal',
            league='Major League'
        )
        db.session.add(match)
    
    # BEER LEAGUE - Quarti di finale (Martedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=placeholder_id,
            team2_id=placeholder_id,
            date=tournament_dates['quarterfinals_bl'],
            time=match_time,
            phase='quarterfinal',
            league='Beer League'
        )
        db.session.add(match)
    
    # MAJOR LEAGUE - Semifinali (Giovedì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=placeholder_id,
            team2_id=placeholder_id,
            date=tournament_dates['semifinals_ml'],
            time=match_time,
            phase='semifinal',
            league='Major League'
        )
        db.session.add(match)
    
    # BEER LEAGUE - Semifinali (Venerdì)
    for i, match_time in enumerate(tournament_times['playoff_times']):
        match = Match(
            team1_id=placeholder_id,
            team2_id=placeholder_id,
            date=tournament_dates['semifinals_bl'],
            time=match_time,
            phase='semifinal',
            league='Beer League'
        )
        db.session.add(match)
    
    # FINALI (Sabato) - Major League
    for i, match_time in enumerate(tournament_times['final_times_ml']):
        match = Match(
            team1_id=placeholder_id,
            team2_id=placeholder_id,
            date=tournament_dates['finals'],
            time=match_time,
            phase='final',
            league='Major League'
        )
        db.session.add(match)
    
    # FINALI (Sabato) - Beer League
    for i, match_time in enumerate(tournament_times['final_times_bl']):
        match = Match(
            team1_id=placeholder_id,
            team2_id=placeholder_id,
            date=tournament_dates['finals'],
            time=match_time,
            phase='final',
            league='Beer League'
        )
        db.session.add(match)

# Aggiungi questa route al tuo app.py per debug

@app.route('/debug_match_numbers')
def debug_match_numbers():
    """Debug: mostra i numeri delle partite e le loro descrizioni."""
    
    matches = Match.query.order_by(Match.date, Match.time).all()
    debug_info = []
    
    for match in matches:
        info = match.debug_match_info()
        
        # Aggiungi le descrizioni che dovrebbe mostrare
        if match.phase != 'group':
            description = match.get_playoff_description()
            info['expected_team1'] = description['team1']
            info['expected_team2'] = description['team2']
            info['actual_team1'] = match.get_team1_display_name()
            info['actual_team2'] = match.get_team2_display_name()
        
        debug_info.append(info)
    
    # Mostra solo le finali per ora
    finals_info = [info for info in debug_info if info.get('phase') == 'final']
    
    flash(f'Debug finali: {finals_info}', 'info')
    return redirect(url_for('schedule'))

# Alternative: Route per forzare la ricalcolo delle descrizioni
@app.route('/fix_descriptions', methods=['POST'])
def fix_descriptions():
    """Forza la ricalcolo delle descrizioni delle partite."""
    
    # Trova le partite problematiche (46 e 48)
    problematic_matches = Match.query.filter(
        Match.phase == 'final',
        Match.league == 'Beer League'
    ).all()
    
    for match in problematic_matches:
        print(f"Match {match.get_match_number()}: {match.get_team1_display_name()} vs {match.get_team2_display_name()}")
        
        # Verifica se la descrizione è corretta
        description = match.get_playoff_description()
        print(f"  Expected: {description['team1']} vs {description['team2']}")
    
    flash('Descrizioni verificate - vedi console per dettagli', 'info')
    return redirect(url_for('schedule'))



@app.route('/schedule', methods=['GET', 'POST'])
def schedule():

    
    if request.method == 'POST':
        # Reset + genera tutto il calendario
        Match.query.delete()
        
        # Reset team stats
        teams = Team.query.all()
        for team in teams:
            team.wins = 0
            team.losses = 0
            team.draws = 0
            team.goals_for = 0
            team.goals_against = 0
            team.points = 0
        
        db.session.commit()
        
        # Usa la funzione corretta
        generate_complete_tournament_simple()
        return redirect(url_for('schedule'))
    
    # Il resto della logica rimane uguale
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
    except Exception as e:
        # Se c'è un errore, restituisci date di fallback
        current_year = datetime.now().year
        return {
            'tournament_dates': {
                'qualification_day1': {
                    'date': datetime(current_year, 7, 13).date(),
                    'formatted': f'13/07/{current_year}',
                    'day_name_it': 'Sabato'
                },
                'qualification_day2': {
                    'date': datetime(current_year, 7, 14).date(), 
                    'formatted': f'14/07/{current_year}',
                    'day_name_it': 'Domenica'
                }
            }
        }
    


def debug_match_descriptions():
    """Stampa le descrizioni delle partite per debugging."""
    matches = Match.query.order_by(Match.date, Match.time).all()
    
    print("\n=== DEBUG: Descrizioni Partite ===")
    for match in matches:
        print(f"Partita {match.get_match_number()}: {match.get_team1_display_name()} vs {match.get_team2_display_name()}")
        print(f"  - Data: {match.date} {match.time}")
        print(f"  - Fase: {match.phase} ({match.league if match.league else 'N/A'})")
        print()

# Route di debug (opzionale)
@app.route('/debug_matches')
def debug_matches():
    debug_match_descriptions()
    flash('Descrizioni partite stampate nella console', 'info')
    return redirect(url_for('schedule'))

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
    
    # Ottieni il parametro di riferimento per tornare alla posizione corretta
    return_anchor = request.args.get('return_anchor', '')
    
    if request.method == 'POST':
        team1_score_str = request.form.get('team1_score')
        team2_score_str = request.form.get('team2_score')
        
        if team1_score_str and team2_score_str:
            old_team1_score = match.team1_score
            old_team2_score = match.team2_score
            
            match.team1_score = int(team1_score_str)
            match.team2_score = int(team2_score_str)
            
            update_team_stats(match, old_team1_score, old_team2_score)
            
            db.session.commit()
            flash('Risultato della partita registrato')
            
            # Dopo aver salvato, torna alla posizione corretta
            if return_anchor:
                return redirect(url_for('schedule') + f'#{return_anchor}')
            else:
                return redirect(url_for('match_detail', match_id=match_id))
    
    # Ottieni le statistiche per questa partita specifica
    team1_players = match.team1.players if match.team1 else []
    team2_players = match.team2.players if match.team2 else []
    
    # Crea un dizionario per le statistiche di questa partita
    match_stats = {}
    
    # Se esiste la tabella PlayerMatchStats, usala
    try:
        for player in team1_players + team2_players:
            stats = PlayerMatchStats.query.filter_by(
                player_id=player.id,
                match_id=match.id
            ).first()
            
            if stats:
                match_stats[player.id] = {
                    'goals': stats.goals,
                    'assists': stats.assists,
                    'penalties': stats.penalties
                }
            else:
                match_stats[player.id] = {
                    'goals': 0,
                    'assists': 0,
                    'penalties': 0
                }
    except:
        # Se la tabella non esiste, usa valori vuoti
        for player in team1_players + team2_players:
            match_stats[player.id] = {
                'goals': 0,
                'assists': 0,
                'penalties': 0
            }
    
    return render_template('match_detail.html', 
                           match=match, 
                           team1_players=team1_players, 
                           team2_players=team2_players, 
                           match_stats=match_stats,
                           return_anchor=return_anchor)

@app.route('/match/<int:match_id>/update_player_stats', methods=['POST'])
def update_player_stats(match_id):
    """Aggiorna le statistiche dei giocatori SOLO per questa partita specifica."""
    match = Match.query.get_or_404(match_id)
    return_anchor = request.form.get('return_anchor', '')
    
    try:
        # Assicurati che la tabella PlayerMatchStats esista
        if not db.inspect(db.engine).has_table('player_match_stats'):
            flash('Errore: Sistema statistiche per partita non disponibile', 'danger')
            return redirect(url_for('match_detail', match_id=match_id))
        
        # Ottieni tutti i giocatori di entrambe le squadre
        all_players = []
        if match.team1:
            all_players.extend(match.team1.players)
        if match.team2:
            all_players.extend(match.team2.players)
        
        # Aggiorna le statistiche SOLO per questa partita
        for player in all_players:
            # Leggi i valori dal form
            goals = int(request.form.get(f'player_{player.id}_goals', 0))
            assists = int(request.form.get(f'player_{player.id}_assists', 0))
            penalties = int(request.form.get(f'player_{player.id}_penalties', 0))
            
            # Trova o crea le statistiche per questo giocatore in questa partita
            stats = PlayerMatchStats.query.filter_by(
                player_id=player.id,
                match_id=match_id
            ).first()
            
            if not stats:
                # Crea nuove statistiche per questa partita
                stats = PlayerMatchStats(
                    player_id=player.id,
                    match_id=match_id,
                    goals=goals,
                    assists=assists,
                    penalties=penalties
                )
                db.session.add(stats)
            else:
                # Aggiorna le statistiche esistenti per questa partita
                stats.goals = goals
                stats.assists = assists
                stats.penalties = penalties
        
        db.session.commit()
        flash('Statistiche della partita aggiornate con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'aggiornamento delle statistiche: {str(e)}', 'danger')
    
    # Torna alla pagina match_detail con l'anchor
    if return_anchor:
        return redirect(url_for('match_detail', match_id=match_id) + f'?return_anchor={return_anchor}')
    else:
        return redirect(url_for('match_detail', match_id=match_id))

# Aggiorna anche la funzione per il calcolo dei totali nelle classifiche
def get_player_statistics_for_standings():
    """Calcola le statistiche totali dei giocatori sommando tutte le partite."""
    
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            # Nuovo sistema: calcola totali dalle statistiche per partita
            players_stats = []
            
            # Query per ottenere i totali per ogni giocatore
            from sqlalchemy import func
            totals = db.session.query(
                PlayerMatchStats.player_id,
                func.sum(PlayerMatchStats.goals).label('total_goals'),
                func.sum(PlayerMatchStats.assists).label('total_assists'),
                func.sum(PlayerMatchStats.penalties).label('total_penalties')
            ).group_by(PlayerMatchStats.player_id).all()
            
            for total in totals:
                player = Player.query.get(total.player_id)
                if player and (total.total_goals > 0 or total.total_assists > 0 or total.total_penalties > 0):
                    # Aggiungi proprietà temporanee per il template
                    player.display_goals = total.total_goals or 0
                    player.display_assists = total.total_assists or 0
                    player.display_penalties = total.total_penalties or 0
                    players_stats.append(player)
            
            return players_stats
        else:
            # Fallback al sistema vecchio
            return Player.query.filter(
                (Player.goals > 0) | (Player.assists > 0) | (Player.penalties > 0)
            ).all()
    
    except Exception as e:
        print(f"Errore nel calcolo statistiche: {e}")
        # Fallback completo
        return Player.query.filter(
            (Player.goals > 0) | (Player.assists > 0) | (Player.penalties > 0)
        ).all()


# # Aggiorna la route standings per usare il nuovo sistema
# @app.route('/standings')
# def standings():
#     # Group stage standings
#     group_standings = {}
#     for group in ['A', 'B', 'C', 'D']:
#         teams = Team.query.filter_by(group=group).order_by(
#             Team.points.desc(), 
#             (Team.goals_for - Team.goals_against).desc(),
#             Team.goals_for.desc()
#         ).all()
#         group_standings[group] = teams
    
#     # Player statistics - usa il nuovo sistema
#     try:
#         if db.inspect(db.engine).has_table('player_match_stats'):
#             # Nuovo sistema: calcola totali dalle partite
#             from sqlalchemy import func
            
#             # Query per i migliori marcatori
#             top_scorers_query = db.session.query(
#                 Player,
#                 func.sum(PlayerMatchStats.goals).label('total_goals')
#             ).join(PlayerMatchStats).group_by(Player.id).having(
#                 func.sum(PlayerMatchStats.goals) > 0
#             ).order_by(func.sum(PlayerMatchStats.goals).desc()).limit(10)
            
#             top_scorers = []
#             for player, total_goals in top_scorers_query:
#                 player.display_goals = total_goals
#                 top_scorers.append(player)
            
#             # Query per i migliori assistman
#             top_assists_query = db.session.query(
#                 Player,
#                 func.sum(PlayerMatchStats.assists).label('total_assists')
#             ).join(PlayerMatchStats).group_by(Player.id).having(
#                 func.sum(PlayerMatchStats.assists) > 0
#             ).order_by(func.sum(PlayerMatchStats.assists).desc()).limit(10)
            
#             top_assists = []
#             for player, total_assists in top_assists_query:
#                 player.display_assists = total_assists
#                 top_assists.append(player)
            
#             # Query per le penalità
#             most_penalties_query = db.session.query(
#                 Player,
#                 func.sum(PlayerMatchStats.penalties).label('total_penalties')
#             ).join(PlayerMatchStats).group_by(Player.id).having(
#                 func.sum(PlayerMatchStats.penalties) > 0
#             ).order_by(func.sum(PlayerMatchStats.penalties).desc()).limit(10)
            
#             most_penalties = []
#             for player, total_penalties in most_penalties_query:
#                 player.display_penalties = total_penalties
#                 most_penalties.append(player)
                
#         else:
#             # Fallback al sistema vecchio
#             top_scorers = Player.query.filter(Player.goals > 0).order_by(Player.goals.desc()).limit(10).all()
#             top_assists = Player.query.filter(Player.assists > 0).order_by(Player.assists.desc()).limit(10).all()
#             most_penalties = Player.query.filter(Player.penalties > 0).order_by(Player.penalties.desc()).limit(10).all()
            
#             for player in top_scorers:
#                 player.display_goals = player.goals
#             for player in top_assists:
#                 player.display_assists = player.assists
#             for player in most_penalties:
#                 player.display_penalties = player.penalties
    
#     except Exception as e:
#         print(f"Errore nelle statistiche: {e}")
#         # Fallback completo
#         top_scorers = []
#         top_assists = []
#         most_penalties = []
    
#     return render_template('standings.html', 
#                           group_standings=group_standings,
#                           top_scorers=top_scorers,
#                           top_assists=top_assists,
#                           most_penalties=most_penalties)

@app.route('/standings')
def standings():
    # Group stage standings - usa l'ordinamento per gironi
    group_standings = {}
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).order_by(
            Team.points.desc(), 
            (Team.goals_for - Team.goals_against).desc(),
            Team.goals_for.desc(),
            Team.group_order  # Aggiungi ordinamento come tiebreaker finale
        ).all()
        group_standings[group] = teams
    
    # Player statistics - usa il nuovo sistema
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            # Nuovo sistema: calcola totali dalle partite
            from sqlalchemy import func
            
            # Query per i migliori marcatori
            top_scorers_query = db.session.query(
                Player,
                func.sum(PlayerMatchStats.goals).label('total_goals')
            ).join(PlayerMatchStats).group_by(Player.id).having(
                func.sum(PlayerMatchStats.goals) > 0
            ).order_by(func.sum(PlayerMatchStats.goals).desc()).limit(10)
            
            top_scorers = []
            for player, total_goals in top_scorers_query:
                player.display_goals = total_goals
                top_scorers.append(player)
            
            # Query per i migliori assistman
            top_assists_query = db.session.query(
                Player,
                func.sum(PlayerMatchStats.assists).label('total_assists')
            ).join(PlayerMatchStats).group_by(Player.id).having(
                func.sum(PlayerMatchStats.assists) > 0
            ).order_by(func.sum(PlayerMatchStats.assists).desc()).limit(10)
            
            top_assists = []
            for player, total_assists in top_assists_query:
                player.display_assists = total_assists
                top_assists.append(player)
            
            # Query per le penalità
            most_penalties_query = db.session.query(
                Player,
                func.sum(PlayerMatchStats.penalties).label('total_penalties')
            ).join(PlayerMatchStats).group_by(Player.id).having(
                func.sum(PlayerMatchStats.penalties) > 0
            ).order_by(func.sum(PlayerMatchStats.penalties).desc()).limit(10)
            
            most_penalties = []
            for player, total_penalties in most_penalties_query:
                player.display_penalties = total_penalties
                most_penalties.append(player)
                
        else:
            # Fallback al sistema vecchio
            top_scorers = Player.query.filter(Player.goals > 0).order_by(Player.goals.desc()).limit(10).all()
            top_assists = Player.query.filter(Player.assists > 0).order_by(Player.assists.desc()).limit(10).all()
            most_penalties = Player.query.filter(Player.penalties > 0).order_by(Player.penalties.desc()).limit(10).all()
            
            for player in top_scorers:
                player.display_goals = player.goals
            for player in top_assists:
                player.display_assists = player.assists
            for player in most_penalties:
                player.display_penalties = player.penalties
    
    except Exception as e:
        print(f"Errore nelle statistiche: {e}")
        # Fallback completo
        top_scorers = []
        top_assists = []
        most_penalties = []
    
    return render_template('standings.html', 
                          group_standings=group_standings,
                          top_scorers=top_scorers,
                          top_assists=top_assists,
                          most_penalties=most_penalties)

# Funzione helper per verificare le statistiche di un giocatore
def get_player_match_stats_summary(player_id):
    """Ottiene un riassunto delle statistiche di un giocatore in tutte le partite."""
    
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            stats = PlayerMatchStats.query.filter_by(player_id=player_id).all()
            
            summary = {
                'matches_played': len(stats),
                'total_goals': sum(stat.goals for stat in stats),
                'total_assists': sum(stat.assists for stat in stats),
                'total_penalties': sum(stat.penalties for stat in stats),
                'match_details': []
            }
            
            for stat in stats:
                match = Match.query.get(stat.match_id)
                if match:
                    summary['match_details'].append({
                        'match_id': match.id,
                        'opponent': 'vs TBD' if not match.team1 or not match.team2 else 
                                   f"vs {match.team2.name}" if match.team1_id == Player.query.get(player_id).team_id 
                                   else f"vs {match.team1.name}",
                        'goals': stat.goals,
                        'assists': stat.assists,
                        'penalties': stat.penalties,
                        'date': match.date.strftime('%d/%m/%Y')
                    })
            
            return summary
    except Exception as e:
        print(f"Errore nel calcolo summary: {e}")
    
    return None

@app.template_filter('datetime')
def format_datetime(value, format='%d/%m/%Y'):
    return value.strftime(format)

@app.template_filter('timeformat')
def format_time(value, format='%H:%M'):
    return value.strftime(format)

@app.template_filter('player_total_goals')
def player_total_goals(player):
    """Template filter per ottenere i gol totali."""
    try:
        if hasattr(player, 'match_stats') and player.match_stats:
            return sum(stat.goals for stat in player.match_stats)
    except:
        pass
    return getattr(player, 'goals', 0)

@app.template_filter('player_total_assists')
def player_total_assists(player):
    """Template filter per ottenere gli assist totali."""
    try:
        if hasattr(player, 'match_stats') and player.match_stats:
            return sum(stat.assists for stat in player.match_stats)
    except:
        pass
    return getattr(player, 'assists', 0)

@app.template_filter('player_total_penalties')
def player_total_penalties(player):
    """Template filter per ottenere le penalità totali."""
    try:
        if hasattr(player, 'match_stats') and player.match_stats:
            return sum(stat.penalties for stat in player.match_stats)
    except:
        pass
    return getattr(player, 'penalties', 0)


def get_player_total_stats():
    """Ottiene le statistiche totali di tutti i giocatori."""
    players = Player.query.all()
    player_stats = []
    
    for player in players:
        if player.match_stats:  # Solo se ha giocato almeno una partita
            player_stats.append({
                'player': player,
                'total_goals': player.total_goals,
                'total_assists': player.total_assists,
                'total_penalties': player.total_penalties,
                'total_points': player.total_points,
                'matches_played': len(player.match_stats)
            })
    
    return player_stats



def update_team_stats(match, old_team1_score=None, old_team2_score=None):
    """Aggiorna le statistiche delle squadre e controlla aggiornamenti playoff automatici."""
    team1 = match.team1
    team2 = match.team2

    # Se esistono vecchi punteggi, sottraiamo quei valori dalle statistiche delle squadre
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

    # *** AGGIORNAMENTI AUTOMATICI PLAYOFF ***
    
    # 1. QUALIFICAZIONI COMPLETATE → AGGIORNA QUARTI
    if match.phase == 'group' and all_group_matches_completed():
        print("🎯 Tutte le qualificazioni completate! Aggiornamento quarti automatico...")
        try:
            update_playoff_brackets()
            print("✅ Quarti aggiornati automaticamente!")
        except Exception as e:
            print(f"❌ Errore aggiornamento quarti: {e}")
    
    # 2. QUARTI COMPLETATI PER UNA LEGA → AGGIORNA SEMIFINALI DI QUELLA LEGA
    if match.phase == 'quarterfinal':
        league = match.league
        if league and all_phase_matches_completed('quarterfinal', league):
            print(f"🎯 Quarti {league} completati! Aggiornamento semifinali automatico...")
            try:
                update_semifinals(league)
                print(f"✅ Semifinali {league} aggiornate automaticamente!")
            except Exception as e:
                print(f"❌ Errore aggiornamento semifinali {league}: {e}")
    
    # 3. SEMIFINALI COMPLETATE PER UNA LEGA → AGGIORNA FINALI DI QUELLA LEGA
    if match.phase == 'semifinal':
        league = match.league
        if league and all_phase_matches_completed('semifinal', league):
            print(f"🎯 Semifinali {league} completate! Aggiornamento finali automatico...")
            try:
                update_finals(league)
                print(f"✅ Finali {league} aggiornate automaticamente!")
            except Exception as e:
                print(f"❌ Errore aggiornamento finali {league}: {e}")




def all_group_matches_completed():
    incomplete_matches = Match.query.filter_by(phase='group').filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    return incomplete_matches == 0
    

@app.route('/force_update_playoffs', methods=['POST'])
def force_update_playoffs():
    """Forza l'aggiornamento dei playoff."""
    try:
        if all_group_matches_completed():
            update_playoff_brackets()
            flash('🎯 Playoff aggiornati con successo!', 'success')
        else:
            flash('⚠️ Le qualificazioni devono essere completate prima di aggiornare i playoff.', 'warning')
    except Exception as e:
        flash(f'❌ Errore durante l\'aggiornamento: {str(e)}', 'danger')
    
    return redirect(url_for('schedule'))


def update_playoff_brackets():
    """Aggiorna i tabelloni playoff con le squadre reali qualificate."""
    
    print("🔄 Inizio aggiornamento playoff brackets...")
    
    # Verifica che tutte le qualificazioni siano completate
    if not all_group_matches_completed():
        print("❌ Le qualificazioni non sono ancora completate")
        return False
    
    # Get team standings by group
    standings = {}
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).order_by(
            Team.points.desc(), 
            (Team.goals_for - Team.goals_against).desc(),
            Team.goals_for.desc()
        ).all()
        standings[group] = teams
        print(f"📊 Girone {group}: {[f'{t.name}({t.points}pts)' for t in teams]}")
    
    # Verifica che ogni girone abbia almeno 4 squadre
    for group in ['A', 'B', 'C', 'D']:
        if len(standings[group]) < 4:
            print(f"❌ Girone {group} ha solo {len(standings[group])} squadre!")
            return False
    
    # Update Major League quarterfinals
    major_quarterfinals = Match.query.filter_by(
        phase='quarterfinal', league='Major League'
    ).order_by(Match.time).all()

    print(f"🏆 Trovati {len(major_quarterfinals)} quarti ML da aggiornare")
    
    if len(major_quarterfinals) >= 4:
        # Accoppiamenti Major League (primi 2 di ogni girone)
        matchups = [
            (standings['D'][0], standings['C'][1]),  # 1°D vs 2°C
            (standings['A'][0], standings['B'][1]),  # 1°A vs 2°B
            (standings['C'][0], standings['A'][1]),  # 1°C vs 2°A
            (standings['B'][0], standings['D'][1])   # 1°B vs 2°D
        ]
        
        for i, (team1, team2) in enumerate(matchups):
            if i < len(major_quarterfinals):
                match = major_quarterfinals[i]
                old_team1 = match.team1.name if match.team1 else "TBD"
                old_team2 = match.team2.name if match.team2 else "TBD"
                
                match.team1_id = team1.id
                match.team2_id = team2.id
                
                print(f"🔄 Quarto ML {i+1}: {old_team1} vs {old_team2} → {team1.name} vs {team2.name}")
        
    # Update Beer League quarterfinals  
    beer_quarterfinals = Match.query.filter_by(
        phase='quarterfinal', league='Beer League'
    ).order_by(Match.time).all()

    print(f"🍺 Trovati {len(beer_quarterfinals)} quarti BL da aggiornare")
    
    if len(beer_quarterfinals) >= 4:
        # Accoppiamenti Beer League (3° e 4° di ogni girone)
        matchups = [
            (standings['B'][2], standings['A'][3]),  # 3°B vs 4°A
            (standings['D'][2], standings['C'][3]),  # 3°D vs 4°C
            (standings['A'][2], standings['D'][3]),  # 3°A vs 4°D
            (standings['C'][2], standings['B'][3])   # 3°C vs 4°B
        ]
        
        for i, (team1, team2) in enumerate(matchups):
            if i < len(beer_quarterfinals):
                match = beer_quarterfinals[i]
                old_team1 = match.team1.name if match.team1 else "TBD"
                old_team2 = match.team2.name if match.team2 else "TBD"
                
                match.team1_id = team1.id
                match.team2_id = team2.id
                
                print(f"🔄 Quarto BL {i+1}: {old_team1} vs {old_team2} → {team1.name} vs {team2.name}")
    
    db.session.commit()
    print("✅ Playoff brackets aggiornati con successo!")
    return True

def all_quarterfinals_completed(league):
    incomplete_matches = Match.query.filter_by(
        phase='quarterfinal', league=league
    ).filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    return incomplete_matches == 0

def update_semifinals(league):
    """Aggiorna le semifinali con vincitori e perdenti dei quarti di finale per una specifica lega."""
    
    # Ottieni i quarti di finale completati per questa lega
    quarterfinals = Match.query.filter_by(
        phase='quarterfinal', league=league
    ).order_by(Match.time).all()
    
    # Ottieni le semifinali per questa lega
    semifinals = Match.query.filter_by(
        phase='semifinal', league=league
    ).order_by(Match.time).all()
    
    print(f"\n=== DEBUG update_semifinals for {league} ===")
    print(f"Quarti trovati: {len(quarterfinals)}")
    print(f"Semifinali trovate: {len(semifinals)}")
    
    # Verifica che tutti i quarti siano completati
    if len(quarterfinals) < 4:
        print(f"Errore: Trovati solo {len(quarterfinals)} quarti invece di 4")
        return
    
    for i, qf in enumerate(quarterfinals):
        if not qf.is_completed:
            print(f"Errore: Quarto {qf.team1.name} vs {qf.team2.name} non completato")
            return
        print(f"Quarto {i+1}: {qf.team1.name} {qf.team1_score}-{qf.team2_score} {qf.team2.name}, Vincitore: {qf.winner.name if qf.winner else 'Nessuno'}")
    
    if len(semifinals) >= 4:
        # Le prime 2 semifinali sono per i perdenti (5°-8° posto)
        # Le ultime 2 semifinali sono per i vincitori (1°-4° posto)
        
        # SEMIFINALI PERDENTI (5°-8° posto)
        loser_qf3 = quarterfinals[2].team1 if quarterfinals[2].winner == quarterfinals[2].team2 else quarterfinals[2].team2
        loser_qf4 = quarterfinals[3].team1 if quarterfinals[3].winner == quarterfinals[3].team2 else quarterfinals[3].team2
        
        semifinals[0].team1_id = loser_qf3.id
        semifinals[0].team2_id = loser_qf4.id
        print(f"Semifinale 0 (perdenti): {loser_qf3.name} vs {loser_qf4.name}")
        
        loser_qf1 = quarterfinals[0].team1 if quarterfinals[0].winner == quarterfinals[0].team2 else quarterfinals[0].team2
        loser_qf2 = quarterfinals[1].team1 if quarterfinals[1].winner == quarterfinals[1].team2 else quarterfinals[1].team2
        
        semifinals[1].team1_id = loser_qf1.id
        semifinals[1].team2_id = loser_qf2.id
        print(f"Semifinale 1 (perdenti): {loser_qf1.name} vs {loser_qf2.name}")
        
        # SEMIFINALI VINCITORI (1°-4° posto)
        winner_qf3 = quarterfinals[2].winner
        winner_qf4 = quarterfinals[3].winner
        
        semifinals[2].team1_id = winner_qf3.id
        semifinals[2].team2_id = winner_qf4.id
        print(f"Semifinale 2 (vincitori): {winner_qf3.name} vs {winner_qf4.name}")
        
        winner_qf1 = quarterfinals[0].winner
        winner_qf2 = quarterfinals[1].winner
        
        semifinals[3].team1_id = winner_qf1.id
        semifinals[3].team2_id = winner_qf2.id
        print(f"Semifinale 3 (vincitori): {winner_qf1.name} vs {winner_qf2.name}")
        
        print(f"Semifinali {league} aggiornate con successo!")
    else:
        print(f"Errore: Trovate solo {len(semifinals)} semifinali invece di 4")
    
    db.session.commit()


def all_semifinals_completed(league):
    incomplete_matches = Match.query.filter_by(
        phase='semifinal', league=league
    ).filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    return incomplete_matches == 0


def update_finals(league):
    """Aggiorna le finali con vincitori e perdenti delle semifinali per una specifica lega."""
    
    # Ottieni le semifinali completate per questa lega
    semifinals = Match.query.filter_by(
        phase='semifinal', league=league
    ).order_by(Match.time).all()
    
    # Ottieni le finali per questa lega
    finals = Match.query.filter_by(
        phase='final', league=league
    ).order_by(Match.time).all()
    
    print(f"\n=== DEBUG update_finals for {league} ===")
    print(f"Semifinali trovate: {len(semifinals)}")
    print(f"Finali trovate: {len(finals)}")
    
    # Verifica che tutte le semifinali siano completate
    if len(semifinals) < 4:
        print(f"Errore: Trovate solo {len(semifinals)} semifinali invece di 4")
        return
    
    for i, sf in enumerate(semifinals):
        if not sf.is_completed:
            print(f"Semifinale {i+1}: {sf.team1.name} vs {sf.team2.name} - NON COMPLETATA")
            return
        print(f"Semifinale {i+1}: {sf.team1.name} {sf.team1_score}-{sf.team2_score} {sf.team2.name}, Vincitore: {sf.winner.name}")
    
    if len(finals) >= 4:
        # Finali nell'ordine: 7°/8°, 5°/6°, 3°/4°, 1°/2°
        
        # FINALE 7°/8° posto: Perdenti delle semifinali perdenti
        loser_sf_losers_1 = semifinals[0].team1 if semifinals[0].winner == semifinals[0].team2 else semifinals[0].team2
        loser_sf_losers_2 = semifinals[1].team1 if semifinals[1].winner == semifinals[1].team2 else semifinals[1].team2
        
        finals[0].team1_id = loser_sf_losers_1.id
        finals[0].team2_id = loser_sf_losers_2.id
        print(f"Finale 7°/8°: {loser_sf_losers_1.name} vs {loser_sf_losers_2.name}")
        
        # FINALE 5°/6° posto: Vincitori delle semifinali perdenti
        winner_sf_losers_1 = semifinals[0].winner
        winner_sf_losers_2 = semifinals[1].winner
        
        finals[1].team1_id = winner_sf_losers_1.id
        finals[1].team2_id = winner_sf_losers_2.id
        print(f"Finale 5°/6°: {winner_sf_losers_1.name} vs {winner_sf_losers_2.name}")
        
        # FINALE 3°/4° posto: Perdenti delle semifinali vincitori
        loser_sf_winners_1 = semifinals[2].team1 if semifinals[2].winner == semifinals[2].team2 else semifinals[2].team2
        loser_sf_winners_2 = semifinals[3].team1 if semifinals[3].winner == semifinals[3].team2 else semifinals[3].team2
        
        finals[2].team1_id = loser_sf_winners_1.id
        finals[2].team2_id = loser_sf_winners_2.id
        print(f"Finale 3°/4°: {loser_sf_winners_1.name} vs {loser_sf_winners_2.name}")
        
        # FINALE 1°/2° posto: Vincitori delle semifinali vincitori
        winner_sf_winners_1 = semifinals[2].winner
        winner_sf_winners_2 = semifinals[3].winner
        
        finals[3].team1_id = winner_sf_winners_1.id
        finals[3].team2_id = winner_sf_winners_2.id
        print(f"Finale 1°/2°: {winner_sf_winners_1.name} vs {winner_sf_winners_2.name}")
        
        print(f"Finali {league} aggiornate con successo!")
    else:
        print(f"Errore: Trovate solo {len(finals)} finali invece di 4")
    
    db.session.commit()





@app.route('/debug_playoff_progression')
def debug_playoff_progression():
    """Debug: mostra la progressione dei playoff."""
    
    info = []
    
    for league in ['Major League', 'Beer League']:
        league_info = {'league': league, 'quarterfinals': [], 'semifinals': [], 'finals': []}
        
        # Quarti
        quarterfinals = Match.query.filter_by(phase='quarterfinal', league=league).order_by(Match.time).all()
        for qf in quarterfinals:
            qf_info = {
                'teams': f"{qf.team1.name} vs {qf.team2.name}",
                'score': f"{qf.team1_score}-{qf.team2_score}" if qf.is_completed else "Non giocata",
                'winner': qf.winner.name if qf.winner else "Nessuno"
            }
            league_info['quarterfinals'].append(qf_info)
        
        # Semifinali
        semifinals = Match.query.filter_by(phase='semifinal', league=league).order_by(Match.time).all()
        for sf in semifinals:
            sf_info = {
                'teams': f"{sf.team1.name} vs {sf.team2.name}",
                'score': f"{sf.team1_score}-{sf.team2_score}" if sf.is_completed else "Non giocata",
                'winner': sf.winner.name if sf.winner else "Nessuno"
            }
            league_info['semifinals'].append(sf_info)
        
        # Finali
        finals = Match.query.filter_by(phase='final', league=league).order_by(Match.time).all()
        for f in finals:
            f_info = {
                'teams': f"{f.team1.name} vs {f.team2.name}",
                'score': f"{f.team1_score}-{f.team2_score}" if f.is_completed else "Non giocata",
                'winner': f.winner.name if f.winner else "Nessuno"
            }
            league_info['finals'].append(f_info)
        
        info.append(league_info)
    
    flash(f'Debug playoff progression: {info}', 'info')
    return redirect(url_for('schedule'))


def get_player_match_stats_summary(player_id):
    """Ottiene un riassunto delle statistiche di un giocatore in tutte le partite."""
    
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            stats = PlayerMatchStats.query.filter_by(player_id=player_id).all()
            
            summary = {
                'matches_played': len(stats),
                'total_goals': sum(stat.goals for stat in stats),
                'total_assists': sum(stat.assists for stat in stats),
                'total_penalties': sum(stat.penalties for stat in stats),
                'match_details': []
            }
            
            for stat in stats:
                match = Match.query.get(stat.match_id)
                if match:
                    summary['match_details'].append({
                        'match_id': match.id,
                        'opponent': 'vs TBD' if not match.team1 or not match.team2 else 
                                   f"vs {match.team2.name}" if match.team1_id == Player.query.get(player_id).team_id 
                                   else f"vs {match.team1.name}",
                        'goals': stat.goals,
                        'assists': stat.assists,
                        'penalties': stat.penalties,
                        'date': match.date.strftime('%d/%m/%Y')
                    })
            
            return summary
    except Exception as e:
        print(f"Errore nel calcolo summary: {e}")
    
    return None

@app.route('/migrate_player_stats', methods=['POST'])
def migrate_player_stats():
    """Migra le statistiche esistenti al nuovo sistema."""
    try:
        # Trova tutti i giocatori con statistiche nel vecchio sistema
        players = Player.query.filter(
            (Player.goals > 0) | (Player.assists > 0) | (Player.penalties > 0)
        ).all()
        
        for player in players:
            # Se ha statistiche nel vecchio sistema, crea una entry "generale"
            if player.goals > 0 or player.assists > 0 or player.penalties > 0:
                # Trova una partita di esempio per questo giocatore
                sample_match = Match.query.filter(
                    (Match.team1_id == player.team_id) | (Match.team2_id == player.team_id)
                ).filter_by(phase='group').first()
                
                if sample_match:
                    # Crea statistiche per quella partita (temporaneo)
                    existing_stats = PlayerMatchStats.query.filter_by(
                        player_id=player.id,
                        match_id=sample_match.id
                    ).first()
                    
                    if not existing_stats:
                        stats = PlayerMatchStats(
                            player_id=player.id,
                            match_id=sample_match.id,
                            goals=player.goals,
                            assists=player.assists,
                            penalties=player.penalties
                        )
                        db.session.add(stats)
                
                # Reset delle statistiche nel vecchio sistema
                player.goals = 0
                player.assists = 0
                player.penalties = 0
        
        db.session.commit()
        flash('Migrazione completata! Le statistiche sono state spostate al nuovo sistema.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la migrazione: {str(e)}', 'danger')
    
    return redirect(url_for('index'))



@app.route('/debug_player_stats')
def debug_player_stats():
    """Debug: mostra le statistiche dei giocatori."""
    stats_info = []
    
    players = Player.query.limit(5).all()  # Prime 5 per test
    for player in players:
        player_info = {
            'name': player.name,
            'team': player.team.name,
            'match_stats_count': len(player.match_stats),
            'total_goals': player.total_goals,
            'total_assists': player.total_assists,
            'total_penalties': player.total_penalties
        }
        stats_info.append(player_info)
    
    flash(f'Debug player stats: {stats_info}', 'info')
    return redirect(url_for('standings'))


@app.route('/init_db')
def init_db():
    try:
        # Crea solo le tabelle dei modelli esistenti
        db.create_all()
        flash('Database inizializzato con successo!', 'success')
    except Exception as e:
        flash(f'Errore durante l\'inizializzazione: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/groups')
def groups():
    groups = {}
    all_teams = Team.query.all()
    
    for group in ['A', 'B', 'C', 'D']:
        # Ordina le squadre per group_order all'interno del girone
        teams = Team.query.filter_by(group=group).order_by(Team.group_order, Team.name).all()
        groups[group] = teams
    
    # Calcola statistiche dei gironi
    groups_stats = {
        'complete': sum(1 for group in ['A', 'B', 'C', 'D'] if len(groups[group]) == 4),
        'incomplete': sum(1 for group in ['A', 'B', 'C', 'D'] if 0 < len(groups[group]) < 4),
        'overfull': sum(1 for group in ['A', 'B', 'C', 'D'] if len(groups[group]) > 4),
        'total_teams': len(all_teams)
    }
    
    return render_template('groups.html', groups=groups, all_teams=all_teams, groups_stats=groups_stats)


@app.route('/update_team_order', methods=['POST'])
def update_team_order():
    """Aggiorna l'ordine delle squadre all'interno di un girone."""
    data = request.json
    group = data.get('group')
    team_ids = data.get('team_ids', [])
    
    try:
        # Aggiorna l'ordinamento per ogni squadra
        for index, team_id in enumerate(team_ids):
            team = Team.query.get(team_id)
            if team and team.group == group:
                team.group_order = index + 1
        
        db.session.commit()
        return {'success': True, 'message': f'Ordine squadre del Girone {group} aggiornato con successo'}
    
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'Errore durante l\'aggiornamento: {str(e)}'}, 500

@app.route('/migrate_team_order', methods=['POST'])
def migrate_team_order():
    """Migra i dati esistenti aggiungendo il campo group_order."""
    try:
        # Per ogni girone, assegna un ordine basato sull'ID o nome
        for group in ['A', 'B', 'C', 'D']:
            teams = Team.query.filter_by(group=group).order_by(Team.id).all()
            for index, team in enumerate(teams):
                team.group_order = index + 1
        
        # Squadre senza girone
        unassigned_teams = Team.query.filter_by(group=None).all()
        for team in unassigned_teams:
            team.group_order = 0
        
        db.session.commit()
        flash('Migrazione dell\'ordinamento completata con successo!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la migrazione: {str(e)}', 'danger')
    
    return redirect(url_for('groups'))


@app.route('/migrate_database', methods=['POST'])
def migrate_database():
    """Migra il database aggiungendo il campo group_order se non esiste."""
    try:
        # Controlla se la colonna group_order esiste già
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('team')]
        
        if 'group_order' not in columns:
            # Aggiungi la colonna group_order
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE team ADD COLUMN group_order INTEGER DEFAULT 0'))
                conn.commit()
            
            # Assegna ordini esistenti
            for group in ['A', 'B', 'C', 'D']:
                teams = Team.query.filter_by(group=group).order_by(Team.id).all()
                for index, team in enumerate(teams):
                    team.group_order = index + 1
            
            # Squadre senza girone
            unassigned_teams = Team.query.filter_by(group=None).all()
            for team in unassigned_teams:
                team.group_order = 0
            
            db.session.commit()
            flash('Database migrato con successo! Campo group_order aggiunto.', 'success')
        else:
            flash('Il campo group_order esiste già nel database.', 'info')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la migrazione del database: {str(e)}', 'danger')
    
    return redirect(url_for('index'))



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
    """Genera i quarti di finale solo dopo che tutte le qualificazioni sono completate"""
    if not all_group_matches_completed():
        return False
    
    # Date dei playoff
    playoff_dates = {
        'ML_quarterfinals': datetime(2025, 7, 15).date(),  # Lunedì  
        'BL_quarterfinals': datetime(2025, 7, 16).date(),  # Martedì
    }
    quarterfinal_times = [time(19, 30), time(20, 15), time(21, 0), time(21, 45)]
    
    # Elimina eventuali quarti di finale già esistenti
    Match.query.filter_by(phase='quarterfinal').delete()
    
    # Ottieni le classifiche dei gironi
    standings = {}
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).order_by(
            Team.points.desc(), 
            (Team.goals_for - Team.goals_against).desc(),
            Team.goals_for.desc()
        ).all()
        standings[group] = teams
    
    # Verifica che ogni girone abbia almeno 4 squadre
    for group in ['A', 'B', 'C', 'D']:
        if len(standings[group]) < 4:
            print(f"Errore: Il girone {group} ha solo {len(standings[group])} squadre")
            return False
    
    # Major League Quarterfinals
    ml_matchups = [
        (standings['C'][0], standings['D'][1]),  # 1C vs 2D
        (standings['B'][0], standings['C'][1]),  # 1B vs 2C  
        (standings['D'][0], standings['A'][1]),  # 1D vs 2A
        (standings['A'][0], standings['B'][1]),  # 1A vs 2B
    ]
    
    for i, (team1, team2) in enumerate(ml_matchups):
        match = Match(
            team1_id=team1.id,
            team2_id=team2.id,
            date=playoff_dates['ML_quarterfinals'],
            time=quarterfinal_times[i],
            phase='quarterfinal',
            league='Major League'
        )
        db.session.add(match)
    
    # Beer League Quarterfinals  
    bl_matchups = [
        (standings['B'][2], standings['C'][3]),  # 3B vs 4C
        (standings['D'][2], standings['A'][3]),  # 3D vs 4A
        (standings['A'][2], standings['B'][3]),  # 3A vs 4B
        (standings['C'][2], standings['D'][3]),  # 3C vs 4D
    ]
    
    for i, (team1, team2) in enumerate(bl_matchups):
        match = Match(
            team1_id=team1.id,
            team2_id=team2.id,
            date=playoff_dates['BL_quarterfinals'],
            time=quarterfinal_times[i],
            phase='quarterfinal',
            league='Beer League'
        )
        db.session.add(match)
    
    db.session.commit()
    return True


def generate_semifinals():
    """Genera le semifinali solo dopo che tutti i quarti sono completati"""
    if not (all_quarterfinals_completed('Major League') and all_quarterfinals_completed('Beer League')):
        return False
    
    # Date dei playoff
    playoff_dates = {
        'ML_semifinals': datetime(2025, 7, 18).date(),
        'BL_semifinals': datetime(2025, 7, 19).date(),
    }
    
    # Elimina eventuali semifinali già esistenti
    Match.query.filter_by(phase='semifinal').delete()
    Match.query.filter_by(phase='placement').delete()  # Anche le partite di piazzamento
    
    # Ottieni i risultati dei quarti di finale
    ml_quarterfinals = Match.query.filter_by(
        phase='quarterfinal', league='Major League'
    ).order_by(Match.time).all()
    
    bl_quarterfinals = Match.query.filter_by(
        phase='quarterfinal', league='Beer League'
    ).order_by(Match.time).all()
    
    if len(ml_quarterfinals) != 4 or len(bl_quarterfinals) != 4:
        return False
    
    # Verifica che tutti i quarti siano completati
    for match in ml_quarterfinals + bl_quarterfinals:
        if not match.is_completed:
            return False
    
    semifinal_times = [time(19, 30), time(20, 15), time(21, 0), time(21, 45)]
    
    # Major League Semifinals
    # SF1: Vincitore QF1 vs Vincitore QF2
    sf1 = Match(
        team1_id=ml_quarterfinals[0].winner.id,
        team2_id=ml_quarterfinals[1].winner.id,
        date=playoff_dates['ML_semifinals'],
        time=semifinal_times[2],  # 21:00
        phase='semifinal',
        league='Major League'
    )
    db.session.add(sf1)
    
    # SF2: Vincitore QF3 vs Vincitore QF4
    sf2 = Match(
        team1_id=ml_quarterfinals[2].winner.id,
        team2_id=ml_quarterfinals[3].winner.id,
        date=playoff_dates['ML_semifinals'],
        time=semifinal_times[3],  # 21:45
        phase='semifinal',
        league='Major League'
    )
    db.session.add(sf2)
    
    # Major League Placement matches (5°-8° posto)
    # PM1: Perdente QF1 vs Perdente QF2
    pm1 = Match(
        team1_id=ml_quarterfinals[0].team1_id if ml_quarterfinals[0].winner.id == ml_quarterfinals[0].team2_id else ml_quarterfinals[0].team2_id,
        team2_id=ml_quarterfinals[1].team1_id if ml_quarterfinals[1].winner.id == ml_quarterfinals[1].team2_id else ml_quarterfinals[1].team2_id,
        date=playoff_dates['ML_semifinals'],
        time=semifinal_times[0],  # 19:30
        phase='placement',
        league='Major League'
    )
    db.session.add(pm1)
    
    # PM2: Perdente QF3 vs Perdente QF4  
    pm2 = Match(
        team1_id=ml_quarterfinals[2].team1_id if ml_quarterfinals[2].winner.id == ml_quarterfinals[2].team2_id else ml_quarterfinals[2].team2_id,
        team2_id=ml_quarterfinals[3].team1_id if ml_quarterfinals[3].winner.id == ml_quarterfinals[3].team2_id else ml_quarterfinals[3].team2_id,
        date=playoff_dates['ML_semifinals'],
        time=semifinal_times[1],  # 20:15
        phase='placement',
        league='Major League'
    )
    db.session.add(pm2)
    
    # Beer League Semifinals (stesso schema)
    sf3 = Match(
        team1_id=bl_quarterfinals[0].winner.id,
        team2_id=bl_quarterfinals[1].winner.id,
        date=playoff_dates['BL_semifinals'],
        time=semifinal_times[2],
        phase='semifinal',
        league='Beer League'
    )
    db.session.add(sf3)
    
    sf4 = Match(
        team1_id=bl_quarterfinals[2].winner.id,
        team2_id=bl_quarterfinals[3].winner.id,
        date=playoff_dates['BL_semifinals'],
        time=semifinal_times[3],
        phase='semifinal',
        league='Beer League'
    )
    db.session.add(sf4)
    
    # Beer League Placement matches
    pm3 = Match(
        team1_id=bl_quarterfinals[0].team1_id if bl_quarterfinals[0].winner.id == bl_quarterfinals[0].team2_id else bl_quarterfinals[0].team2_id,
        team2_id=bl_quarterfinals[1].team1_id if bl_quarterfinals[1].winner.id == bl_quarterfinals[1].team2_id else bl_quarterfinals[1].team2_id,
        date=playoff_dates['BL_semifinals'],
        time=semifinal_times[0],
        phase='placement',
        league='Beer League'
    )
    db.session.add(pm3)
    
    pm4 = Match(
        team1_id=bl_quarterfinals[2].team1_id if bl_quarterfinals[2].winner.id == bl_quarterfinals[2].team2_id else bl_quarterfinals[2].team2_id,
        team2_id=bl_quarterfinals[3].team1_id if bl_quarterfinals[3].winner.id == bl_quarterfinals[3].team2_id else bl_quarterfinals[3].team2_id,
        date=playoff_dates['BL_semifinals'],
        time=semifinal_times[1],
        phase='placement',
        league='Beer League'
    )
    db.session.add(pm4)
    
    db.session.commit()
    return True


def generate_finals():
    """Genera le finali solo dopo che tutte le semifinali sono completate"""
    if not (all_semifinals_completed('Major League') and all_semifinals_completed('Beer League')):
        return False
    
    # Verifica che anche le partite di piazzamento siano completate
    ml_placement = Match.query.filter_by(phase='placement', league='Major League').all()
    bl_placement = Match.query.filter_by(phase='placement', league='Beer League').all()
    
    for match in ml_placement + bl_placement:
        if not match.is_completed:
            return False
    
    playoff_dates = {
        'finals': datetime(2025, 7, 20).date()
    }
    
    # Elimina eventuali finali già esistenti
    Match.query.filter_by(phase='final').delete()
    
    # Ottieni i risultati delle semifinali e piazzamenti
    ml_semifinals = Match.query.filter_by(phase='semifinal', league='Major League').order_by(Match.time).all()
    bl_semifinals = Match.query.filter_by(phase='semifinal', league='Beer League').order_by(Match.time).all()
    
    if len(ml_semifinals) != 2 or len(bl_semifinals) != 2:
        return False
    
    if len(ml_placement) != 2 or len(bl_placement) != 2:
        return False
    
    final_times = {
        'Major League': [time(12, 0), time(14, 0), time(16, 0), time(18, 0)],
        'Beer League': [time(11, 0), time(13, 0), time(15, 0), time(17, 0)]
    }
    
    # Major League Finals
    # 7°/8° posto
    f1 = Match(
        team1_id=ml_placement[0].team1_id if ml_placement[0].winner.id == ml_placement[0].team2_id else ml_placement[0].team2_id,
        team2_id=ml_placement[1].team1_id if ml_placement[1].winner.id == ml_placement[1].team2_id else ml_placement[1].team2_id,
        date=playoff_dates['finals'],
        time=final_times['Major League'][0],
        phase='final',
        league='Major League'
    )
    db.session.add(f1)
    
    # 5°/6° posto
    f2 = Match(
        team1_id=ml_placement[0].winner.id,
        team2_id=ml_placement[1].winner.id,
        date=playoff_dates['finals'],
        time=final_times['Major League'][1],
        phase='final',
        league='Major League'
    )
    db.session.add(f2)
    
    # 3°/4° posto
    f3 = Match(
        team1_id=ml_semifinals[0].team1_id if ml_semifinals[0].winner.id == ml_semifinals[0].team2_id else ml_semifinals[0].team2_id,
        team2_id=ml_semifinals[1].team1_id if ml_semifinals[1].winner.id == ml_semifinals[1].team2_id else ml_semifinals[1].team2_id,
        date=playoff_dates['finals'],
        time=final_times['Major League'][2],
        phase='final',
        league='Major League'
    )
    db.session.add(f3)
    
    # 1°/2° posto
    f4 = Match(
        team1_id=ml_semifinals[0].winner.id,
        team2_id=ml_semifinals[1].winner.id,
        date=playoff_dates['finals'],
        time=final_times['Major League'][3],
        phase='final',
        league='Major League'
    )
    db.session.add(f4)
    
    # Beer League Finals (stesso schema)
    # 7°/8° posto
    f5 = Match(
        team1_id=bl_placement[0].team1_id if bl_placement[0].winner.id == bl_placement[0].team2_id else bl_placement[0].team2_id,
        team2_id=bl_placement[1].team1_id if bl_placement[1].winner.id == bl_placement[1].team2_id else bl_placement[1].team2_id,
        date=playoff_dates['finals'],
        time=final_times['Beer League'][0],
        phase='final',
        league='Beer League'
    )
    db.session.add(f5)
    
    # 5°/6° posto
    f6 = Match(
        team1_id=bl_placement[0].winner.id,
        team2_id=bl_placement[1].winner.id,
        date=playoff_dates['finals'],
        time=final_times['Beer League'][1],
        phase='final',
        league='Beer League'
    )
    db.session.add(f6)
    
    # 3°/4° posto
    f7 = Match(
        team1_id=bl_semifinals[0].team1_id if bl_semifinals[0].winner.id == bl_semifinals[0].team2_id else bl_semifinals[0].team2_id,
        team2_id=bl_semifinals[1].team1_id if bl_semifinals[1].winner.id == bl_semifinals[1].team2_id else bl_semifinals[1].team2_id,
        date=playoff_dates['finals'],
        time=final_times['Beer League'][2],
        phase='final',
        league='Beer League'
    )
    db.session.add(f7)
    
    # 1°/2° posto
    f8 = Match(
        team1_id=bl_semifinals[0].winner.id,
        team2_id=bl_semifinals[1].winner.id,
        date=playoff_dates['finals'],
        time=final_times['Beer League'][3],
        phase='final',
        league='Beer League'
    )
    db.session.add(f8)
    
    db.session.commit()
    return True

def format_tournament_dates():
    """
    Restituisce le date del torneo formattate per la visualizzazione.
    """
    dates = get_tournament_dates()
    formatted = {}
    
    # Mappatura mesi italiano
    mesi_italiani = {
        'January': 'Gennaio',
        'February': 'Febbraio', 
        'March': 'Marzo',
        'April': 'Aprile',
        'May': 'Maggio',
        'June': 'Giugno',
        'July': 'Luglio',
        'August': 'Agosto',
        'September': 'Settembre',
        'October': 'Ottobre',
        'November': 'Novembre',
        'December': 'Dicembre'
    }
    
    for key, date_obj in dates.items():
        month_english = date_obj.strftime('%B')
        month_italian = mesi_italiani.get(month_english, month_english)
        
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
            }.get(date_obj.strftime('%A'), date_obj.strftime('%A')),
            'month_name_it': month_italian  # AGGIUNTO: nome mese in italiano
        }
    
    return formatted

# Aggiungi queste funzioni al tuo app.py per popolare il database con dati di esempio

import random
from datetime import datetime

# Lista di nomi italiani per i giocatori
NOMI_GIOCATORI = [
    "Marco Rossi", "Luca Bianchi", "Andrea Verdi", "Matteo Ferrari", "Alessandro Romano",
    "Stefano Russo", "Francesco Marino", "Giovanni Greco", "Antonio Ricci", "Davide Costa",
    "Simone Bruno", "Federico Villa", "Riccardo Gallo", "Michele Conti", "Gabriele Fontana",
    "Nicola Serra", "Daniele Barbieri", "Claudio Leone", "Fabio Longo", "Roberto Marini",
    "Paolo Santoro", "Vincenzo Rinaldi", "Sergio Palumbo", "Giorgio De Luca", "Mario Pellegrini",
    "Enrico Lombardi", "Alberto Rizzo", "Flavio Moretti", "Dario Ferretti", "Massimo Testa",
    "Giulio Mancini", "Emanuele Battaglia", "Lorenzo D'Angelo", "Cristian Fabbri", "Mattia Benedetti",
    "Simone Martinelli", "Alessio Neri", "Fabrizio Gentile", "Diego Orlando", "Tommaso Silvestri",
    "Andrea Caruso", "Marco Ferrara", "Luca De Santis", "Stefano Morelli", "Antonio Farina",
    "Francesco Caputo", "Giovanni Ferri", "Matteo Bianco", "Alessandro De Rosa", "Davide Gatti",
    "Nicola Esposito", "Federico Sanna", "Michele Colombo", "Riccardo Marchetti", "Gabriele Coppola",
    "Daniele Monti", "Claudio Basile", "Fabio Mazza", "Roberto Pace", "Paolo Amato",
    "Vincenzo Ruggiero", "Sergio Carbone", "Giorgio Fiore", "Mario Donati", "Enrico Cattaneo",
    "Alberto Giordano", "Flavio Messina", "Dario Parisi", "Massimo Sala", "Giulio Antonelli",
    "Emanuele Belli", "Lorenzo Rossetti", "Cristian Martini", "Mattia Sorrentino", "Simone Rizzi",
    "Alessio Guerra", "Fabrizio Vitale", "Diego Mariani", "Tommaso Pagano", "Andrea Negri"
]

def create_teams():
    """Crea le 16 squadre del torneo se non esistono già."""
    
    # Lista delle squadre del torneo
    team_names = [
        'DRUNK JUNIORS', 'LE PADELLE', 'ANIMALS TEAM', 'BARRHOCK',
        'AROSIO CAPITALS', 'TRE SEJDLAR', 'FLORY MOTOS', 'GIUGADUU DALA LIPPA',
        'YELLOWSTONE', 'BARDOLINO TEAM DOC', 'TIRABUSCION', 'HOCKTAIL',
        'CATERPILLARS', 'I GAMB ROTT', 'PEPPA BEER', 'ORIGINAL TWINS'
    ]
    
    created_teams = 0
    
    for team_name in team_names:
        # Controlla se la squadra esiste già
        existing_team = Team.query.filter_by(name=team_name).first()
        
        if not existing_team:
            # Crea la squadra
            team = Team(name=team_name)
            db.session.add(team)
            created_teams += 1
            print(f"Creata squadra: {team_name}")
    
    if created_teams > 0:
        db.session.commit()
        print(f"Totale squadre create: {created_teams}")
    else:
        print("Tutte le squadre esistono già")
    
    return created_teams

def populate_sample_data():
    """Popola il database con dati di esempio per squadre, giocatori, partite e risultati."""
    
    try:
        # Step 0: Crea le squadre se non esistono
        print("Step 0: Creazione squadre...")
        created_teams = create_teams()
        
        # Verifica che ora abbiamo tutte le 16 squadre
        teams = Team.query.all()
        if len(teams) != 16:
            flash(f'Errore: Servono esattamente 16 squadre, trovate {len(teams)}. Squadre create: {created_teams}', 'danger')
            return
        
        # Step 1: Assegna le squadre ai gironi come da lista
        team_assignments = {
            'A': ['DRUNK JUNIORS', 'LE PADELLE', 'ANIMALS TEAM', 'BARRHOCK'],
            'B': ['AROSIO CAPITALS', 'TRE SEJDLAR', 'FLORY MOTOS', 'GIUGADUU DALA LIPPA'],
            'C': ['YELLOWSTONE', 'BARDOLINO TEAM DOC', 'TIRABUSCION', 'HOCKTAIL'],
            'D': ['CATERPILLARS', 'I GAMB ROTT', 'PEPPA BEER', 'ORIGINAL TWINS']
        }
        
        print("Step 1: Assegnazione gironi...")
        for group, team_names in team_assignments.items():
            for team_name in team_names:
                team = Team.query.filter_by(name=team_name).first()
                if team:
                    team.group = group
                    # Reset statistiche squadra
                    team.wins = 0
                    team.losses = 0
                    team.draws = 0
                    team.goals_for = 0
                    team.goals_against = 0
                    team.points = 0
                else:
                    print(f"ATTENZIONE: Squadra {team_name} non trovata!")
        
        db.session.commit()
        
        # Step 2: Popola giocatori per ogni squadra
        print("Step 2: Creazione giocatori...")
        populate_players()
        
        # Step 3: Genera il calendario delle qualificazioni
        print("Step 3: Generazione calendario...")
        generate_complete_tournament_simple()
        
        # Step 4: Reset e popola risultati delle qualificazioni con statistiche realistiche
        print("Step 4: Popolamento risultati qualificazioni...")
        reset_all_player_match_stats()  # Reset statistiche esistenti
        populate_qualification_results()
        
        # Step 5: Aggiorna i playoff con le squadre qualificate
        print("Step 5: Aggiornamento playoff...")
        update_playoff_brackets()
        
        flash('Database popolato con successo con dati di esempio!', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Errore dettagliato: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Errore durante la popolazione del database: {str(e)}', 'danger')


def reset_all_player_match_stats():
    """Reset di tutte le statistiche dei giocatori (sia vecchio che nuovo sistema)."""
    
    # Reset statistiche nel nuovo sistema (PlayerMatchStats)
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            PlayerMatchStats.query.delete()
            print("Reset statistiche PlayerMatchStats completato")
    except Exception as e:
        print(f"Errore nel reset PlayerMatchStats: {e}")
    
    # Reset statistiche nel vecchio sistema (Player)
    try:
        players = Player.query.all()
        for player in players:
            player.goals = 0
            player.assists = 0
            player.penalties = 0
        print("Reset statistiche Player completato")
    except Exception as e:
        print(f"Errore nel reset statistiche Player: {e}")
    
    db.session.commit()


@app.route('/create_teams_only', methods=['POST'])
def create_teams_only():
    """Route per creare solo le squadre."""
    try:
        created_teams = create_teams()
        if created_teams > 0:
            flash(f'{created_teams} squadre create con successo!', 'success')
        else:
            flash('Tutte le squadre esistono già', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la creazione delle squadre: {str(e)}', 'danger')
    
    return redirect(url_for('index'))


@app.route('/populate_step_by_step', methods=['POST'])
def populate_step_by_step():
    """Popola il database passo per passo per debug."""
    try:
        step = request.form.get('step', '1')
        
        if step == '0':
            # Solo creazione squadre
            created_teams = create_teams()
            flash(f'Step 0 completato: {created_teams} squadre create', 'success')
            
        elif step == '1':
            # Solo assegnazione gironi
            team_assignments = {
                'A': ['Barrhock', 'Yellowstone Team', 'Flory Motos', 'Hocktail'],
                'B': ['Original Twins', 'Arosio Capital', 'I Gamb Rott', 'Animal\'s Team'],
                'C': ['Peppa Beer', 'Tirabiscion', 'Bardolino', 'Le Padelle'],
                'D': ['Drunk Junior', 'Tre Sejdlàr', 'HC Caterpillars', 'Giugaduu Dala Lippa']
            }
            
            for group, team_names in team_assignments.items():
                for team_name in team_names:
                    team = Team.query.filter_by(name=team_name).first()
                    if team:
                        team.group = group
            
            db.session.commit()
            flash('Step 1 completato: Gironi assegnati', 'success')
            
        elif step == '2':
            # Solo giocatori
            populate_players()
            flash('Step 2 completato: Giocatori creati', 'success')
            
        elif step == '3':
            # Solo calendario
            generate_qualification_matches_simple()
            generate_all_playoff_matches_simple()
            flash('Step 3 completato: Calendario generato', 'success')
            
        elif step == '4':
            # Solo risultati qualificazioni
            reset_all_player_match_stats()
            populate_qualification_results()
            flash('Step 4 completato: Risultati qualificazioni', 'success')
            
        elif step == '5':
            # Solo aggiornamento playoff
            update_playoff_brackets()
            flash('Step 5 completato: Playoff aggiornati', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nello step {step}: {str(e)}', 'danger')
    
    return redirect(url_for('index'))


# def populate_players():
#     """Aggiunge giocatori casuali a ogni squadra."""
    
#     teams = Team.query.all()
#     nome_index = 0
    
#     for team in teams:
#         # Elimina giocatori esistenti per questa squadra
#         Player.query.filter_by(team_id=team.id).delete()
        
#         # Aggiungi 8-12 giocatori per squadra
#         num_players = random.randint(8, 12)
#         team_points = 0
        
#         for i in range(num_players):
#             if nome_index >= len(NOMI_GIOCATORI):
#                 nome_index = 0  # Ricomincia se finiscono i nomi
            
#             player_name = NOMI_GIOCATORI[nome_index]
#             nome_index += 1
            
#             # Determina se è tesserato (70% probabilità)
#             is_registered = random.random() < 0.7
            
#             if is_registered:
#                 # Assegna categoria casuale ma bilanciata
#                 if team_points < 10:  # Se abbiamo ancora spazio per giocatori forti
#                     category_choice = random.choices(
#                         ['LNA/LNB', '1a Lega', '2a Lega'],
#                         weights=[0.1, 0.3, 0.6]  # Più giocatori di categoria bassa
#                     )[0]
#                 else:  # Se siamo vicini al limite
#                     category_choice = random.choices(
#                         ['1a Lega', '2a Lega'],
#                         weights=[0.2, 0.8]  # Solo categorie più basse
#                     )[0]
                
#                 category = category_choice
#             else:
#                 category = None
            
#             # Crea il giocatore
#             player = Player(
#                 name=player_name,
#                 team=team,
#                 is_registered=is_registered,
#                 category=category
#             )
            
#             # Calcola punti tesseramento
#             points = player.registration_points
            
#             # Se aggiungere questo giocatore supererebbe il limite, rendilo non tesserato
#             if team_points + points > 20:
#                 player.is_registered = False
#                 player.category = None
#                 points = 2
            
#             team_points += points
#             db.session.add(player)
            
#             # Se raggiungiamo esattamente 20 punti, smetti di aggiungere tesserati
#             if team_points >= 20:
#                 # Aggiungi il resto come non tesserati
#                 for j in range(i + 1, num_players):
#                     if nome_index >= len(NOMI_GIOCATORI):
#                         nome_index = 0
                    
#                     remaining_player = Player(
#                         name=NOMI_GIOCATORI[nome_index],
#                         team=team,
#                         is_registered=False,
#                         category=None
#                     )
#                     nome_index += 1
#                     db.session.add(remaining_player)
#                 break
    
#     db.session.commit()

# def populate_qualification_results():
#     """Popola i risultati delle partite di qualificazione con dati casuali."""
    
#     # Ottieni tutte le partite di qualificazione
#     qualification_matches = Match.query.filter_by(phase='group').all()
    
#     for match in qualification_matches:
#         # Genera punteggi casuali (0-6 gol per squadra)
#         team1_score = random.randint(0, 6)
#         team2_score = random.randint(0, 6)
        
#         # Salva i punteggi
#         match.team1_score = team1_score
#         match.team2_score = team2_score
        
#         # Aggiorna le statistiche delle squadre
#         update_team_stats(match, None, None)
        
#         # Popola statistiche realistiche dei giocatori per questa partita
#         populate_realistic_player_stats_for_match(match)
    
#     db.session.commit()

# def populate_realistic_player_stats_for_match(match):
#     """Popola le statistiche dei giocatori per una partita specifica in modo realistico."""
    
#     if not match.team1 or not match.team2:
#         return
    
#     team1_players = list(match.team1.players)
#     team2_players = list(match.team2.players)
    
#     if not team1_players or not team2_players:
#         return
    
#     # Distribuisci i gol in modo realistico per la squadra 1
#     distribute_goals_realistically(team1_players, match.team1_score, match.id)
    
#     # Distribuisci i gol in modo realistico per la squadra 2
#     distribute_goals_realistically(team2_players, match.team2_score, match.id)
    
#     # Aggiungi assist e penalità per entrambe le squadre
#     add_assists_and_penalties(team1_players, match.id)
#     add_assists_and_penalties(team2_players, match.id)

# def distribute_goals_realistically(players, total_goals, match_id):
#     """Distribuisce i gol in modo realistico tra i giocatori di una squadra."""
    
#     if total_goals == 0 or not players:
#         # Anche se non ci sono gol, crea record vuoti per tutti i giocatori
#         for player in players:
#             create_or_update_player_match_stats(player.id, match_id, 0, 0, 0)
#         return
    
#     goals_distributed = 0
#     goals_per_player = {}
    
#     # Inizializza tutti i giocatori con 0 gol
#     for player in players:
#         goals_per_player[player.id] = 0
    
#     # Distribuisci i gol uno per uno
#     available_players = players.copy()
    
#     while goals_distributed < total_goals and available_players:
#         # Scegli un giocatore casuale
#         scorer = random.choice(available_players)
#         goals_per_player[scorer.id] += 1
#         goals_distributed += 1
        
#         # Un giocatore può segnare al massimo 3 gol per partita
#         if goals_per_player[scorer.id] >= 3:
#             available_players.remove(scorer)
    
#     # Crea i record delle statistiche per tutti i giocatori
#     for player in players:
#         goals = goals_per_player[player.id]
#         create_or_update_player_match_stats(player.id, match_id, goals, 0, 0)
        
#         # Aggiorna anche le statistiche cumulative (vecchio sistema)
#         player.goals += goals

# def add_assists_and_penalties(players, match_id):
#     """Aggiunge assist e penalità casuali ai giocatori."""
    
#     for player in players:
#         # Ottieni le statistiche esistenti per questo giocatore in questa partita
#         existing_stats = get_player_match_stats(player.id, match_id)
#         goals = existing_stats['goals'] if existing_stats else 0
        
#         # Calcola assist (ogni gol può avere 0-2 assist, più probabili se il giocatore non ha segnato)
#         assists = 0
#         if goals == 0:
#             # I giocatori che non hanno segnato hanno più probabilità di fare assist
#             if random.random() < 0.25:  # 25% probabilità
#                 assists = random.randint(1, 2)
#         else:
#             # I giocatori che hanno segnato hanno meno probabilità di fare anche assist
#             if random.random() < 0.15:  # 15% probabilità
#                 assists = 1
        
#         # Calcola penalità (rare, 5% probabilità)
#         penalties = 0
#         if random.random() < 0.05:
#             penalties = random.choices([1, 2], weights=[0.8, 0.2])[0]  # Più spesso 1 penalità
        
#         # Aggiorna le statistiche
#         create_or_update_player_match_stats(player.id, match_id, goals, assists, penalties)
        
#         # Aggiorna anche le statistiche cumulative (vecchio sistema)
#         player.assists += assists
#         player.penalties += penalties

# def create_or_update_player_match_stats(player_id, match_id, goals, assists, penalties):
#     """Crea o aggiorna le statistiche di un giocatore per una partita specifica."""
    
#     try:
#         # Prova a usare il nuovo sistema (PlayerMatchStats)
#         if db.inspect(db.engine).has_table('player_match_stats'):
#             # Cerca statistiche esistenti
#             existing_stats = PlayerMatchStats.query.filter_by(
#                 player_id=player_id,
#                 match_id=match_id
#             ).first()
            
#             if existing_stats:
#                 # Aggiorna statistiche esistenti
#                 existing_stats.goals = goals
#                 existing_stats.assists = assists
#                 existing_stats.penalties = penalties
#             else:
#                 # Crea nuove statistiche
#                 new_stats = PlayerMatchStats(
#                     player_id=player_id,
#                     match_id=match_id,
#                     goals=goals,
#                     assists=assists,
#                     penalties=penalties
#                 )
#                 db.session.add(new_stats)
        
#     except Exception as e:
#         print(f"Errore nella gestione PlayerMatchStats: {e}")
#         # Se il nuovo sistema non funziona, le statistiche cumulative sono già gestite sopra

# def get_player_match_stats(player_id, match_id):
#     """Ottiene le statistiche di un giocatore per una partita specifica."""
    
#     try:
#         if db.inspect(db.engine).has_table('player_match_stats'):
#             stats = PlayerMatchStats.query.filter_by(
#                 player_id=player_id,
#                 match_id=match_id
#             ).first()
            
#             if stats:
#                 return {
#                     'goals': stats.goals,
#                     'assists': stats.assists,
#                     'penalties': stats.penalties
#                 }
#     except Exception as e:
#         print(f"Errore nel recupero PlayerMatchStats: {e}")
    
#     return None

# Route per attivare la popolazione completa
@app.route('/populate_sample_data', methods=['POST'])
def populate_sample_data_route():
    """Route per popolare il database con dati di esempio."""
    populate_sample_data()
    return redirect(url_for('index'))

# Route per resettare completamente e ripopolare
@app.route('/reset_and_populate', methods=['POST'])
def reset_and_populate():
    """Resetta tutto e ripopola con dati di esempio."""
    try:
        # Reset completo del database
        reset_matches()
        
        # Elimina tutti i giocatori
        Player.query.delete()
        
        # Elimina tutte le squadre
        Team.query.delete()
        
        # Reset statistiche giocatori per partita
        try:
            if db.inspect(db.engine).has_table('player_match_stats'):
                PlayerMatchStats.query.delete()
        except:
            pass
        
        db.session.commit()
        
        # Ripopola tutto da zero
        populate_sample_data()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante il reset e ripopolazione: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

# Funzione helper per verificare l'integrità dei dati
@app.route('/verify_data')
def verify_data():
    """Verifica l'integrità dei dati di esempio."""
    teams = Team.query.all()
    
    verification = []
    for team in teams:
        team_info = {
            'name': team.name,
            'group': team.group,
            'players': len(team.players),
            'total_points': team.player_points_total,
            'matches_played': team.games_played,
            'team_points': team.points
        }
        verification.append(team_info)
    
    flash(f'Verifica completata. Squadre totali: {len(teams)}. Dati: {verification}', 'info')
    return redirect(url_for('teams'))

@app.route('/debug_teams')
def debug_teams():
    """Debug: mostra informazioni sulle squadre."""
    teams = Team.query.all()
    info = []
    
    for team in teams:
        info.append({
            'id': team.id,
            'name': team.name,
            'group': team.group,
            'players': len(team.players) if team.players else 0
        })
    
    flash(f'Debug teams: {info}', 'info')
    return redirect(url_for('teams'))


@app.route('/verify_player_stats')
def verify_player_stats():
    """Verifica le statistiche dei giocatori per debugging."""
    
    # Prendi alcuni giocatori e le loro statistiche
    players = Player.query.limit(10).all()
    stats_info = []
    
    for player in players:
        player_info = {
            'name': player.name,
            'team': player.team.name,
            'total_goals_old': player.goals,
            'total_assists_old': player.assists,
            'total_penalties_old': player.penalties
        }
        
        # Prova a ottenere statistiche dal nuovo sistema
        try:
            if hasattr(player, 'match_stats'):
                total_goals_new = sum(stat.goals for stat in player.match_stats)
                total_assists_new = sum(stat.assists for stat in player.match_stats)
                total_penalties_new = sum(stat.penalties for stat in player.match_stats)
                player_info.update({
                    'total_goals_new': total_goals_new,
                    'total_assists_new': total_assists_new,
                    'total_penalties_new': total_penalties_new,
                    'matches_played': len(player.match_stats)
                })
        except:
            player_info['new_system'] = 'Non disponibile'
        
        stats_info.append(player_info)
    
    flash(f'Statistiche giocatori: {stats_info}', 'info')
    return redirect(url_for('standings'))


# @app.route('/debug_matches')
# def debug_matches_route():
#     """Debug: mostra informazioni sulle partite."""
#     matches = Match.query.all()
#     info = []
    
#     for match in matches[:10]:  # Solo prime 10
#         info.append({
#             'id': match.id,
#             'phase': match.phase,
#             'league': match.league,
#             'team1_id': match.team1_id,
#             'team2_id': match.team2_id,
#             'team1_name': match.team1.name if match.team1 else 'None',
#             'team2_name': match.team2.name if match.team2 else 'None',
#             'score': f"{match.team1_score}-{match.team2_score}" if match.is_completed else "Non giocata"
#         })
    
#     flash(f'Debug matches (prime 10): {info}', 'info')
#     return redirect(url_for('schedule'))

if __name__ == '__main__':
     app.run(debug=True)