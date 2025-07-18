from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time, timedelta
from itertools import combinations
import os
import random
import calendar
import json


import io
import pandas as pd

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
import tempfile

from reportlab.lib.units import inch

# Aggiungi queste importazioni all'inizio del tuo app.py
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# # Configurazione per Railway vs sviluppo locale
# if os.environ.get('RAILWAY_ENVIRONMENT'):
#     # In produzione su Railway
#     app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key-change-this')
#     app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///tournament.db')
#     app.config['DEBUG'] = False
# else:
#     # In sviluppo locale
#     app.config['SECRET_KEY'] = os.urandom(24)
#     app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tournament.db'
#     app.config['DEBUG'] = True
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if os.environ.get('RAILWAY_ENVIRONMENT'):
    # In produzione su Railway con PostgreSQL
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key-change-this')
    database_url = os.environ.get('DATABASE_URL')
    
    # Fix per Railway PostgreSQL (sostituisce postgres:// con postgresql://)
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///tournament.db'
    app.config['DEBUG'] = False
    print(f"🐘 Usando PostgreSQL in produzione")
else:
    # In sviluppo locale con SQLite
    app.config['SECRET_KEY'] = os.urandom(24)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tournament.db'
    app.config['DEBUG'] = True
    print(f"Usando SQLite in sviluppo")

    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Aggiungi dopo l'inizializzazione di db
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Devi effettuare il login per accedere a questa pagina.'

class User(UserMixin, db.Model):
    """Modello per gli utenti del sistema."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' o 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Imposta la password hashata."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica la password."""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Controlla se l'utente è admin."""
        return self.role == 'admin'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            #flash('Login effettuato con successo!', 'success')
            
            # Redirect alla pagina richiesta o alla home
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Username o password errati', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Controlla se l'username esiste già
        if User.query.filter_by(username=username).first():
            flash('Username già esistente', 'danger')
            return render_template('register.html')
        
        # Crea nuovo utente (sempre come 'user', non admin)
        user = User(username=username, role='user')
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registrazione completata! Ora puoi effettuare il login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout effettuato con successo', 'success')
    return redirect(url_for('index'))

# Decoratore personalizzato per admin
def admin_required(f):
    """Decoratore che richiede privilegi di admin."""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Accesso negato. Privilegi di amministratore richiesti.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


def create_admin_user():
    """Crea un utente admin di default se non /esiste."""
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', role='admin')
        admin.set_password('admin12345')  # Cambia questa password!
        db.session.add(admin)
        db.session.commit()
        print("Utente admin creato: admin/admin123")
















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
    category = db.Column(db.String(100))  # LNA/LNB, 1a Lega, 2a Lega, Non tesserato
    
    # Player stats
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    penalties = db.Column(db.Integer, default=0)
    
    @property
    def registration_points(self):
        """Calcola i punti tesseramento secondo le regole del torneo."""
        if not self.is_registered:
            return 0  # Non tesserato = 0 punti
        
        # Mappa punti per categoria
        points_map = {
            'LNA/LNB': 5,     # LNA/LNB = 5 punti
            '1a Lega': 3,     # 1° Lega = 3 punti  
            '2a Lega': 2,     # 2° Lega = 2 punti
            'Femminile': 0,   # Femminile = 0 punti
            'Veterani': 0,     # Veterani = 0 punti
            'Portiere': 0,     # Portiere = 0 punti
            'Old': 0
        }
        return points_map.get(self.category, 0)  # Default 0 punti se categoria non riconosciuta

    

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

    overtime = db.Column(db.Boolean, default=False)  # True se la partita è andata oltre i tempi regolamentari
    shootout = db.Column(db.Boolean, default=False)  # True se decisa ai rigori
    
    phase = db.Column(db.String(20), nullable=False)
    league = db.Column(db.String(20))
    
    @property
    def is_completed(self):
        return self.team1_score is not None and self.team2_score is not None
    
    @property
    def is_regulation_time(self):
        """True se la partita è finita nei tempi regolamentari."""
        return not self.overtime and not self.shootout
    
    # @property
    # def winner(self):
    #     if not self.is_completed:
    #         return None
    #     if self.team1_score > self.team2_score:
    #         return self.team1
    #     elif self.team2_score > self.team1_score:
    #         return self.team2
    #     return None  # Draw (solo per fasi che permettono pareggi)
    

    @property
    def winner(self):
        if not self.is_completed:
            return None
        
        if self.team1_score > self.team2_score:
            return self.team1
        elif self.team2_score > self.team1_score:
            return self.team2
        else:
            # Pareggio: nelle fasi playoff deve essere risolto
            if self.phase in ['quarterfinal', 'semifinal', 'final', 'placement']:
                # Per i playoff, un pareggio senza overtime/rigori è un errore
                if not (self.overtime or self.shootout):
                    raise ValueError(f"Pareggio non risolto nella fase {self.phase}! Deve finire con overtime o rigori.")
            return None  # Pareggio permesso solo nella fase di gruppo


    @property 
    def is_overtime_shootout(self):
        """True se la partita è finita overtime/rigori."""
        return self.overtime or self.shootout


    def get_points_for_team(self, team):
        """Calcola i punti per una squadra specifica secondo il regolamento hockey."""
        if not self.is_completed or not team:
            return 0
        
        is_winner = (self.winner == team)
        is_loser = not is_winner and self.winner is not None
        
        # Sistema punti hockey
        if is_winner:
            if self.is_regulation_time:
                return 3  # Vittoria nei tempi regolamentari
            else:
                return 2  # Vittoria overtime/rigori
        elif is_loser:
            if self.is_overtime_shootout:
                return 1  # Sconfitta overtime/rigori
            else:
                return 0  # Sconfitta nei tempi regolamentari
        else:
            return 1  # Pareggio (se permesso)

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
  
    def get_allowed_overtime_rules(self):
        """Restituisce le regole di overtime/rigori permesse per questa fase."""
        if self.phase == 'quarterfinal':
            return {
                'allow_overtime': False,
                'allow_shootout': True,
                'description': 'Solo rigori (no overtime)'
            }
        elif self.phase == 'semifinal':
            return {
                'allow_overtime': True, 
                'allow_shootout': True,
                'description': 'Overtime + rigori se necessario'
            }
        elif self.phase == 'final' or self.phase == 'placement':
            # Distingui tra finali 1°-4° e 5°-8° per entrambe le leghe
            all_finals = Match.query.filter_by(
                phase=self.phase, 
                league=self.league,
                date=self.date
            ).order_by(Match.time).all()
            
            if len(all_finals) >= 2:
                # Le ultime 2 partite di ogni lega sono sempre 1°-4° posto (3°-4° e 1°-2°)
                if self in all_finals[-2:]:
                    return {
                        'allow_overtime': True,
                        'allow_shootout': True, 
                        'description': 'Finale 1°-4°: Overtime + rigori se necessario'
                    }
            
            # Tutte le altre finali (5°-8° posto) solo rigori
            return {
                'allow_overtime': False,
                'allow_shootout': True,
                'description': 'Finale 5°-8°: Solo rigori (no overtime)'
            }
        else:
            # Fase di gruppo: regole normali
            return {
                'allow_overtime': True,
                'allow_shootout': True,
                'description': 'Overtime + rigori permessi'
            }

class FinalRanking(db.Model):
    """Classifica finale del torneo (posizioni 1-16)."""
    __tablename__ = 'final_ranking'
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    final_position = db.Column(db.Integer, nullable=False)  # 1-16
    league = db.Column(db.String(20), nullable=False)  # Major League o Beer League
    league_position = db.Column(db.Integer, nullable=False)  # 1-8 dentro la lega
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relazioni
    team = db.relationship('Team', backref='final_ranking_entry')
    
    @staticmethod
    def calculate_final_rankings():
        """Calcola e salva le classifiche finali basate sui risultati delle finali."""
        try:
            # Elimina ranking esistenti
            FinalRanking.query.delete()
            
            # Ottieni tutti i risultati delle finali
            final_matches = Match.query.filter_by(phase='final').order_by(Match.time).all()
            
            if not final_matches:
                print("⚠️ Nessuna finale trovata per calcolare la classifica")
                return False
            
            # Separa le finali per lega
            ml_finals = [m for m in final_matches if m.league == 'Major League']
            bl_finals = [m for m in final_matches if m.league == 'Beer League']
            
            rankings = []
            
            # MAJOR LEAGUE - Posizioni 1-8
            if len(ml_finals) >= 4:
                ml_rankings = FinalRanking._process_league_finals(ml_finals, 'Major League', 0)
                rankings.extend(ml_rankings)
            
            # BEER LEAGUE - Posizioni 9-16  
            if len(bl_finals) >= 4:
                bl_rankings = FinalRanking._process_league_finals(bl_finals, 'Beer League', 8)
                rankings.extend(bl_rankings)
            
            # Salva nel database
            for ranking in rankings:
                db.session.add(ranking)
            
            db.session.commit()
            print(f"✅ Classifiche finali calcolate: {len(rankings)} posizioni")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Errore nel calcolo classifiche finali: {e}")
            return False
    
    @staticmethod
    def _process_league_finals(finals, league_name, position_offset):
        """Processa le finali di una lega e restituisce le classifiche."""
        rankings = []
        
        # Ordina le finali per piazzamento (1°/2°, 3°/4°, 5°/6°, 7°/8°)
        # Assumendo che siano ordinate per orario: 7°/8°, 5°/6°, 3°/4°, 1°/2°
        finals_by_placement = {}
        
        for i, match in enumerate(finals):
            if i == 0:  # Prima finale = 7°/8° posto
                placement = "7-8"
            elif i == 1:  # Seconda finale = 5°/6° posto
                placement = "5-6"
            elif i == 2:  # Terza finale = 3°/4° posto
                placement = "3-4"
            elif i == 3:  # Quarta finale = 1°/2° posto
                placement = "1-2"
            
            finals_by_placement[placement] = match
        
        # Calcola le posizioni finali
        positions = {}
        
        # 1°/2° posto
        if "1-2" in finals_by_placement:
            match = finals_by_placement["1-2"]
            if match.is_completed and match.winner:
                winner = match.winner
                loser = match.team1 if match.team2 == winner else match.team2
                positions[1] = winner
                positions[2] = loser
        
        # 3°/4° posto
        if "3-4" in finals_by_placement:
            match = finals_by_placement["3-4"]
            if match.is_completed and match.winner:
                winner = match.winner
                loser = match.team1 if match.team2 == winner else match.team2
                positions[3] = winner
                positions[4] = loser
        
        # 5°/6° posto
        if "5-6" in finals_by_placement:
            match = finals_by_placement["5-6"]
            if match.is_completed and match.winner:
                winner = match.winner
                loser = match.team1 if match.team2 == winner else match.team2
                positions[5] = winner
                positions[6] = loser
        
        # 7°/8° posto
        if "7-8" in finals_by_placement:
            match = finals_by_placement["7-8"]
            if match.is_completed and match.winner:
                winner = match.winner
                loser = match.team1 if match.team2 == winner else match.team2
                positions[7] = winner
                positions[8] = loser
        
        # Crea gli oggetti FinalRanking
        for league_pos in range(1, 9):
            if league_pos in positions:
                team = positions[league_pos]
                final_position = position_offset + league_pos
                
                ranking = FinalRanking(
                    team_id=team.id,
                    final_position=final_position,
                    league=league_name,
                    league_position=league_pos
                )
                rankings.append(ranking)
        
        return rankings
    
    @staticmethod
    def get_team_final_position(team_id):
        """Ottieni la posizione finale di una squadra."""
        ranking = FinalRanking.query.filter_by(team_id=team_id).first()
        return ranking.final_position if ranking else None


def calculate_team_penalty_minutes(team):
    """Calcola i minuti totali di penalità per una squadra."""
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            # Nuovo sistema: usa la durata totale delle penalità
            from sqlalchemy import func
            
            total_penalty_minutes = db.session.query(
                func.sum(PlayerMatchStats.penalties)
            ).join(Player).filter(
                Player.team_id == team.id
            ).scalar()
            
            return total_penalty_minutes or 0
            
        else:
            # Fallback al sistema vecchio (assumendo 2 minuti per penalità)
            total_penalties = sum(player.penalties for player in team.players)
            return total_penalties * 2
        
    except Exception as e:
        print(f"Errore calcolo penalità per {team.name}: {e}")
        return 0

def validate_match_overtime_rules(match):
    """Valida che overtime/shootout rispettino le regole della fase."""
    if not match.is_completed:
        return True, ""
    
    rules = match.get_allowed_overtime_rules()
    
    # Se è in pareggio, deve essere risolto nei playoff
    if (match.team1_score == match.team2_score and 
        match.phase in ['quarterfinal', 'semifinal', 'final', 'placement']):
        
        if not (match.overtime or match.shootout):
            return False, f"Pareggio non permesso in {match.phase}! Deve finire con overtime o rigori."
    
    # Controlla regole overtime
    if match.overtime and not rules['allow_overtime']:
        return False, f"Overtime non permesso in {match.phase}! {rules['description']}"
    
    # Controlla regole shootout
    if match.shootout and not rules['allow_shootout']:
        return False, f"Rigori non permessi in {match.phase}! {rules['description']}"
    
    return True, ""


def get_fair_play_ranking():
    """Calcola la classifica Fair Play."""
    try:
        teams = Team.query.all()
        fair_play_data = []
        
        for team in teams:
            # Calcola minuti di penalità
            penalty_minutes = calculate_team_penalty_minutes(team)
            
            # Ottieni posizione finale (se disponibile)
            final_position = FinalRanking.get_team_final_position(team.id)
            
            # Se non c'è posizione finale, usa la posizione nei gironi come stima
            if final_position is None:
                # Calcola posizione stimata basata sui punti nei gironi
                group_teams = Team.query.filter_by(group=team.group).order_by(
                    Team.points.desc(),
                    (Team.goals_for - Team.goals_against).desc(),
                    Team.goals_for.desc()
                ).all()
                
                group_position = next((i + 1 for i, t in enumerate(group_teams) if t.id == team.id), 5)
                
                # Stima posizione finale (molto approssimativa)
                if group_position <= 2:
                    estimated_final_position = group_position  # Top 2 vanno in Major
                else:
                    estimated_final_position = group_position + 8  # Bottom 2 vanno in Beer
                
                final_position = estimated_final_position
            
            fair_play_data.append({
                'team': team,
                'penalty_minutes': penalty_minutes,
                'final_position': final_position,
                'has_final_ranking': FinalRanking.get_team_final_position(team.id) is not None
            })
        
        # Ordina per Fair Play:
        # 1. Meno minuti di penalità (meglio)
        # 2. Migliore posizione finale (numero più basso = meglio)
        fair_play_data.sort(key=lambda x: (x['penalty_minutes'], -x['final_position']))
        
        return fair_play_data
        
    except Exception as e:
        print(f"Errore calcolo fair play: {e}")
        return []



@app.route('/update_final_rankings', methods=['POST'])
def update_final_rankings():
    """Calcola e aggiorna le classifiche finali."""
    try:
        success = FinalRanking.calculate_final_rankings()
        if success:
            flash('🏆 Classifiche finali calcolate con successo!', 'success')
        else:
            flash('⚠️ Non è possibile calcolare le classifiche finali. Completa prima tutte le finali.', 'warning')
    except Exception as e:
        flash(f'❌ Errore nel calcolo delle classifiche finali: {str(e)}', 'danger')
    
    return redirect(url_for('standings'))

@app.route('/migrate_fair_play', methods=['POST'])
def migrate_fair_play():
    """Migra il database per aggiungere la tabella fair play."""
    try:
        # Crea la tabella se non esiste
        db.create_all()
        #flash('🔧 Migrazione Fair Play completata con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        #flash(f'❌ Errore durante la migrazione Fair Play: {str(e)}', 'danger')
    
    return redirect(url_for('standings'))



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
        {'extend_existing': True}
    )
    
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    
    # Statistiche base
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    penalties = db.Column(db.Integer, default=0)
    penalty_durations = db.Column(db.Text)
    
    # NUOVI CAMPI: Tempi per ogni azione
    goal_times = db.Column(db.Text)  # Es: "15,23,67" per gol al 15°, 23° e 67° minuto
    assist_times = db.Column(db.Text)  # Es: "10,45" per assist al 10° e 45° minuto
    penalty_times = db.Column(db.Text)  # Es: "30" per penalità al 30° minuto
    
    # NUOVO CAMPO: Numero di maglia per questa partita
    jersey_number = db.Column(db.Integer)  # Numero di maglia per questa specifica partita
    
    # Campi esistenti per migliori giocatori
    is_best_player_team1 = db.Column(db.Boolean, default=False)
    is_best_player_team2 = db.Column(db.Boolean, default=False)

    is_removed = db.Column(db.Boolean, default=False)
    
    # Relazioni
    player = db.relationship('Player', backref='match_stats')
    match = db.relationship('Match', backref='player_stats')
    
    def get_goal_times_list(self):
        """Restituisce una lista dei tempi dei gol."""
        if not self.goal_times:
            return []
        return [int(time.strip()) for time in self.goal_times.split(',') if time.strip()]
    
    def set_goal_times_list(self, times_list):
        """Imposta i tempi dei gol da una lista."""
        if times_list:
            self.goal_times = ','.join(map(str, sorted(times_list)))
        else:
            self.goal_times = None
    
    def get_assist_times_list(self):
        """Restituisce una lista dei tempi degli assist."""
        if not self.assist_times:
            return []
        return [int(time.strip()) for time in self.assist_times.split(',') if time.strip()]
    
    def set_assist_times_list(self, times_list):
        """Imposta i tempi degli assist da una lista."""
        if times_list:
            self.assist_times = ','.join(map(str, sorted(times_list)))
        else:
            self.assist_times = None
    
    def get_penalty_times_list(self):
        """Restituisce una lista dei tempi delle penalità."""
        if not self.penalty_times:
            return []
        return [int(time.strip()) for time in self.penalty_times.split(',') if time.strip()]
    
    def set_penalty_times_list(self, times_list):
        """Imposta i tempi delle penalità da una lista."""
        if times_list:
            self.penalty_times = ','.join(map(str, sorted(times_list)))
        else:
            self.penalty_times = None

    def get_penalty_durations_list(self):
        """Restituisce una lista delle durate delle penalità."""
        if not self.penalty_durations:
            return []
        return [float(duration.strip()) for duration in self.penalty_durations.split(',') if duration.strip()]
    
    def set_penalty_durations_list(self, durations_list):
        """Imposta le durate delle penalità da una lista."""
        if durations_list:
            self.penalty_durations = ','.join(str(duration) for duration in durations_list)
        else:
            self.penalty_durations = None
    
    def get_total_penalty_duration(self):
        """Restituisce la durata totale delle penalità."""
        durations = self.get_penalty_durations_list()
        return sum(durations) if durations else 0
    
    def get_penalty_count(self):
        """Restituisce il numero di penalità."""
        durations = self.get_penalty_durations_list()
        return len(durations)
    
    def get_formatted_times_display(self):
        """Restituisce una stringa formattata con tutti i tempi per il display."""
        display_parts = []
        
        if self.goals > 0:
            goal_times = self.get_goal_times_list()
            if goal_times:
                display_parts.append(f"Gol: {', '.join(map(str, goal_times))}'")
        
        if self.assists > 0:
            assist_times = self.get_assist_times_list()
            if assist_times:
                display_parts.append(f"Assist: {', '.join(map(str, assist_times))}'")
        
        # NUOVA LOGICA per penalità con durate
        penalty_times = self.get_penalty_times_list()
        penalty_durations = self.get_penalty_durations_list()
        
        if penalty_times and penalty_durations:
            penalty_info = []
            for i, (time, duration) in enumerate(zip(penalty_times, penalty_durations)):
                penalty_info.append(f"{time}' ({duration}min)")
            
            display_parts.append(f"Penalità: {', '.join(penalty_info)}")
        
        return " | ".join(display_parts) if display_parts else "-"

class TournamentSettings(db.Model):
    """Configurazioni del torneo."""
    __tablename__ = 'tournament_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Date del torneo
    tournament_start_date = db.Column(db.Date)
    qualification_day1 = db.Column(db.Date)
    qualification_day2 = db.Column(db.Date)
    quarterfinals_ml_date = db.Column(db.Date)
    quarterfinals_bl_date = db.Column(db.Date)
    semifinals_ml_date = db.Column(db.Date)
    semifinals_bl_date = db.Column(db.Date)
    finals_date = db.Column(db.Date)
    
    # Orari (salvati come JSON string)
    qualification_times = db.Column(db.Text)  # JSON array
    playoff_times = db.Column(db.Text)       # JSON array
    final_times_ml = db.Column(db.Text)      # JSON array
    final_times_bl = db.Column(db.Text)      # JSON array
    
    # Configurazioni squadre
    max_teams = db.Column(db.Integer, default=16)
    teams_per_group = db.Column(db.Integer, default=4)
    max_registration_points = db.Column(db.Integer, default=20)
    min_players_per_team = db.Column(db.Integer, default=8)
    max_players_per_team = db.Column(db.Integer, default=15)
    
    # Sistema punti
    points_win = db.Column(db.Integer, default=3)
    points_draw = db.Column(db.Integer, default=1)
    points_loss = db.Column(db.Integer, default=0)
    
    # Categorie tesseramento (JSON)
    registration_categories = db.Column(db.Text)  # JSON object
    
    # Sistema playoff
    playoff_system = db.Column(db.String(50), default='standard')  # standard, custom
    quarterfinal_matchups = db.Column(db.Text)  # JSON array
    
    # Configurazioni generali
    tournament_name = db.Column(db.String(200), default='Torneo degli Amici dello Skater')
    auto_update_playoffs = db.Column(db.Boolean, default=True)
    maintenance_mode = db.Column(db.Boolean, default=False)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_settings():
        """Ottieni le configurazioni correnti o crea quelle di default."""
        try:
            # Controlla se la tabella esiste
            if not db.inspect(db.engine).has_table('tournament_settings'):
                print("⚠️ Tabella tournament_settings non trovata, ritorno None")
                return None
            
            settings = TournamentSettings.query.first()
            if not settings:
                print("📝 Nessuna configurazione trovata, creando default...")
                settings = TournamentSettings.create_default()
            return settings
        except Exception as e:
            print(f"❌ Errore nel recupero settings: {e}")
            return None
    
    @staticmethod
    def create_default():
        """Crea configurazioni di default."""
        import json
        from datetime import time
        
        # Date di default (secondo sabato di luglio)
        tournament_dates = get_tournament_dates()
        tournament_times = get_tournament_times()
        
        # Converti i time objects in stringhe per JSON
        qual_times = [t.strftime('%H:%M') for t in tournament_times['qualification_times']]
        playoff_times_str = [t.strftime('%H:%M') for t in tournament_times['playoff_times']]
        final_ml_times = [t.strftime('%H:%M') for t in tournament_times['final_times_ml']]
        final_bl_times = [t.strftime('%H:%M') for t in tournament_times['final_times_bl']]
        
        # Accoppiamenti quarti di finale di default
        default_quarterfinals = [
            {"position": 1, "team1": "1° gruppo D", "team2": "2° gruppo C"},
            {"position": 2, "team1": "1° gruppo A", "team2": "2° gruppo B"},
            {"position": 3, "team1": "1° gruppo C", "team2": "2° gruppo A"},
            {"position": 4, "team1": "1° gruppo B", "team2": "2° gruppo D"}
        ]
        
        # Categorie tesseramento di default
        default_categories = {
            "LNA/LNB": 5,
            "1a Lega": 3,
            "2a Lega": 2,
            "Non tesserato": 2
        }
        
        settings = TournamentSettings(
            tournament_start_date=tournament_dates['qualification_day1'],
            qualification_day1=tournament_dates['qualification_day1'],
            qualification_day2=tournament_dates['qualification_day2'],
            quarterfinals_ml_date=tournament_dates['quarterfinals_ml'],
            quarterfinals_bl_date=tournament_dates['quarterfinals_bl'],
            semifinals_ml_date=tournament_dates['semifinals_ml'],
            semifinals_bl_date=tournament_dates['semifinals_bl'],
            finals_date=tournament_dates['finals'],
            
            qualification_times=json.dumps(qual_times),
            playoff_times=json.dumps(playoff_times_str),
            final_times_ml=json.dumps(final_ml_times),
            final_times_bl=json.dumps(final_bl_times),
            
            quarterfinal_matchups=json.dumps(default_quarterfinals),
            registration_categories=json.dumps(default_categories)
        )
        
        db.session.add(settings)
        db.session.commit()
        return settings
    
    def get_qualification_times_list(self):
        """Ottieni gli orari delle qualificazioni come lista di time objects."""
        import json
        from datetime import time
        if self.qualification_times:
            times_str = json.loads(self.qualification_times)
            return [datetime.strptime(t, '%H:%M').time() for t in times_str]
        return []
    
    def get_playoff_times_list(self):
        """Ottieni gli orari dei playoff come lista di time objects."""
        import json
        from datetime import time
        if self.playoff_times:
            times_str = json.loads(self.playoff_times)
            return [datetime.strptime(t, '%H:%M').time() for t in times_str]
        return []
    
    def get_quarterfinal_matchups_list(self):
        """Ottieni gli accoppiamenti dei quarti come lista."""
        import json
        if self.quarterfinal_matchups:
            return json.loads(self.quarterfinal_matchups)
        return []
    
    def get_registration_categories_dict(self):
        """Ottieni le categorie di tesseramento come dizionario."""
        import json
        if self.registration_categories:
            return json.loads(self.registration_categories)
        return {}

class AllStarTeam(db.Model):
    """All Star Team - giocatori selezionati per posizione."""
    __tablename__ = 'all_star_team'
    
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    position = db.Column(db.String(100), nullable=False)  # 'Portiere', 'Difensore_1', 'Difensore_2', 'Attaccante_1', 'Attaccante_2'
    category = db.Column(db.String(100), nullable=False)  # 'Tesserati', 'Non Tesserati'
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relazioni
    player = db.relationship('Player', backref='all_star_selections')
    
    __table_args__ = (
        db.UniqueConstraint('position', 'category', name='unique_position_category'),
    )



@app.route('/all_star_team')
def all_star_team():
    """Pagina gestione All Star Team."""
    # Ottieni selezioni esistenti
    selections = AllStarTeam.query.all()
    
    # Organizza per categoria e posizione
    all_star_data = {
        'Tesserati': {
            'Portiere': None,
            'Difensore_1': None,
            'Difensore_2': None,
            'Attaccante_1': None,
            'Attaccante_2': None
        },
        'Non Tesserati': {
            'Portiere': None,
            'Difensore_1': None,
            'Difensore_2': None,
            'Attaccante_1': None,
            'Attaccante_2': None
        }
    }
    
    for selection in selections:
        category = selection.category  # Usa direttamente la categoria dal database
        position = selection.position
        if position in all_star_data[category]:
            all_star_data[category][position] = selection.player
    
    # Ottieni tutte le squadre per il dropdown
    teams = Team.query.order_by(Team.name).all()
    
    return render_template('all_star_team.html', 
                         all_star_data=all_star_data, 
                         teams=teams)

@app.route('/get_team_players/<int:team_id>')
def get_team_players(team_id):
    """API per ottenere giocatori di una squadra."""
    players = Player.query.filter_by(team_id=team_id).order_by(Player.name).all()
    
    players_data = []
    for player in players:
        players_data.append({
            'id': player.id,
            'name': player.name,
            'is_registered': player.is_registered
        })
    
    return jsonify(players_data)

@app.route('/update_all_star_selection', methods=['POST'])
def update_all_star_selection():
    """Aggiorna una selezione All Star."""
    try:
        data = request.get_json()
        position = data.get('position')
        player_id = data.get('player_id')
        
        if not position or not player_id:
            return jsonify({'success': False, 'message': 'Dati mancanti'})
        
        player = Player.query.get(player_id)
        if not player:
            return jsonify({'success': False, 'message': 'Giocatore non trovato'})
        
        category = 'Tesserati' if player.is_registered else 'Non Tesserati'
        
        # Rimuovi selezione esistente per questa posizione/categoria
        AllStarTeam.query.filter_by(position=position, category=category).delete()
        
        # Aggiungi nuova selezione
        new_selection = AllStarTeam(
            player_id=player_id,
            position=position,
            category=category
        )
        
        db.session.add(new_selection)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'player_name': player.name,
            'team_name': player.team.name
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/remove_all_star_selection', methods=['POST'])
def remove_all_star_selection():
    """Rimuovi una selezione All Star."""
    try:
        data = request.get_json()
        position = data.get('position')
        category = data.get('category')
        
        AllStarTeam.query.filter_by(position=position, category=category).delete()
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    


# AGGIUNGERE in app.py - Route per auto-save con localStorage

@app.route('/match/<int:match_id>/sync', methods=['POST'])
@login_required
def sync_match_data(match_id):
    """Sincronizza i dati del match dal localStorage al server."""
    match = Match.query.get_or_404(match_id)
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Nessun dato ricevuto'})
        
        saved_data = data.get('data', {})
        timestamp = data.get('timestamp', 0)
        
        # Log per debug
        print(f"📡 Sync match {match_id}: {len(saved_data)} campi ricevuti")
        
        # Aggiorna il risultato se presente
        if 'team1_score' in saved_data and 'team2_score' in saved_data:
            try:
                team1_score = int(saved_data['team1_score']) if saved_data['team1_score'] else None
                team2_score = int(saved_data['team2_score']) if saved_data['team2_score'] else None
                
                if team1_score is not None and team2_score is not None:
                    old_team1_score = match.team1_score
                    old_team2_score = match.team2_score
                    old_overtime = getattr(match, 'overtime', False)
                    old_shootout = getattr(match, 'shootout', False)
                    
                    match.team1_score = team1_score
                    match.team2_score = team2_score
                    
                    # Gestisci overtime e shootout se presenti
                    if 'overtime' in saved_data:
                        match.overtime = saved_data['overtime'] in ['true', True, 'on']
                    if 'shootout' in saved_data:
                        match.shootout = saved_data['shootout'] in ['true', True, 'on']
                    
                    # Aggiorna statistiche squadre se il risultato è cambiato
                    if (old_team1_score != team1_score or old_team2_score != team2_score or 
                        old_overtime != getattr(match, 'overtime', False) or 
                        old_shootout != getattr(match, 'shootout', False)):
                        update_team_stats(match, old_team1_score, old_team2_score, old_overtime, old_shootout)
                        
            except (ValueError, TypeError) as e:
                print(f"❌ Errore conversione punteggi: {e}")
        
        # Aggiorna statistiche giocatori
        all_players = []
        if match.team1:
            all_players.extend(match.team1.players)
        if match.team2:
            all_players.extend(match.team2.players)
        
        for player in all_players:
            try:
                # Estrai dati giocatore
                goals = int(saved_data.get(f'player_{player.id}_goals', 0))
                assists = int(saved_data.get(f'player_{player.id}_assists', 0))
                penalties = float(saved_data.get(f'player_{player.id}_penalties', 0))
                jersey_number = saved_data.get(f'player_{player.id}_jersey_number')
                
                # Gestisci tempi (se presenti)
                goal_times_str = saved_data.get(f'player_{player.id}_goal_times', '')
                assist_times_str = saved_data.get(f'player_{player.id}_assist_times', '')
                penalty_times_str = saved_data.get(f'player_{player.id}_penalty_times', '')
                penalty_durations_str = saved_data.get(f'player_{player.id}_penalty_durations', '')
                
                # Converti tempi in liste
                goal_times = []
                if goal_times_str:
                    goal_times = [int(t.strip()) for t in goal_times_str.split(',') if t.strip().isdigit()]
                
                assist_times = []
                if assist_times_str:
                    assist_times = [int(t.strip()) for t in assist_times_str.split(',') if t.strip().isdigit()]
                
                penalty_times = []
                penalty_durations = []
                if penalty_times_str and penalty_durations_str:
                    penalty_times = [int(t.strip()) for t in penalty_times_str.split(',') if t.strip().isdigit()]
                    penalty_durations = [float(d.strip()) for d in penalty_durations_str.split(',') if d.strip()]
                
                # Calcola durata totale penalità
                total_penalty_duration = sum(penalty_durations) if penalty_durations else penalties
                
                # Gestisci migliori giocatori
                is_best_team1 = saved_data.get('best_player_team1') == str(player.id)
                is_best_team2 = saved_data.get('best_player_team2') == str(player.id)
                
                # Trova o crea statistiche
                stats = PlayerMatchStats.query.filter_by(
                    player_id=player.id,
                    match_id=match.id
                ).first()
                
                if not stats:
                    stats = PlayerMatchStats(
                        player_id=player.id,
                        match_id=match.id,
                        goals=goals,
                        assists=assists,
                        penalties=total_penalty_duration,
                        jersey_number=int(jersey_number) if jersey_number else None,
                        goal_times=','.join(map(str, goal_times)) if goal_times else None,
                        assist_times=','.join(map(str, assist_times)) if assist_times else None,
                        penalty_times=','.join(map(str, penalty_times)) if penalty_times else None,
                        penalty_durations=','.join(map(str, penalty_durations)) if penalty_durations else None,
                        is_best_player_team1=is_best_team1,
                        is_best_player_team2=is_best_team2,
                        is_removed=getattr(player, 'is_removed', False)
                    )
                    db.session.add(stats)
                else:
                    stats.goals = goals
                    stats.assists = assists
                    stats.penalties = total_penalty_duration
                    stats.jersey_number = int(jersey_number) if jersey_number else None
                    stats.goal_times = ','.join(map(str, goal_times)) if goal_times else None
                    stats.assist_times = ','.join(map(str, assist_times)) if assist_times else None
                    stats.penalty_times = ','.join(map(str, penalty_times)) if penalty_times else None
                    stats.penalty_durations = ','.join(map(str, penalty_durations)) if penalty_durations else None
                    stats.is_best_player_team1 = is_best_team1
                    stats.is_best_player_team2 = is_best_team2
                
            except (ValueError, TypeError) as e:
                print(f"❌ Errore statistiche giocatore {player.id}: {e}")
                continue
        
        # Salva tutto
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Sincronizzati {len(saved_data)} campi',
            'new_version': int(timestamp)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Errore sync match {match_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Errore server: {str(e)}'})
# SOSTITUIRE la route quick_save in app.py con questa versione corretta:

@app.route('/match/<int:match_id>/quick_save', methods=['POST'])
@login_required
def quick_save_match(match_id):
    """Salvataggio rapido quando l'utente sta per chiudere la pagina."""
    try:
        # navigator.sendBeacon() invia i dati come text/plain, non JSON
        # Quindi dobbiamo gestire entrambi i casi
        
        content_type = request.content_type
        
        if content_type and 'application/json' in content_type:
            # Richiesta JSON normale
            data = request.get_json()
        else:
            # Richiesta da sendBeacon (text/plain)
            raw_data = request.get_data(as_text=True)
            if raw_data:
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    # Se non è JSON valido, logga e continua
                    print(f"⚠️ Quick save data non JSON: {raw_data[:100]}...")
                    return '', 204
            else:
                data = {}
        
        if not data:
            return '', 204
        
        # Log per debug - salvataggio di emergenza
        print(f"🚨 Quick save match {match_id}: {len(data)} campi (Content-Type: {content_type})")
        
        # Opzionale: salva in una tabella temporanea per recovery
        # Per ora loggiamo semplicemente i campi principali
        if 'team1_score' in data and 'team2_score' in data:
            print(f"   Punteggio: {data.get('team1_score')} - {data.get('team2_score')}")
        
        player_stats = [k for k in data.keys() if k.startswith('player_') and k.endswith('_goals')]
        if player_stats:
            print(f"   Statistiche giocatori: {len(player_stats)} giocatori con dati")
        
        return '', 204  # No Content - salvataggio beacon completato
        
    except Exception as e:
        print(f"❌ Errore quick save: {e}")
        return '', 500
@app.route('/match/<int:match_id>/get_current_data', methods=['GET'])
@login_required
def get_current_match_data(match_id):
    """Restituisce i dati attuali del match per confronto."""
    match = Match.query.get_or_404(match_id)
    
    try:
        # Costruisci i dati attuali del match
        current_data = {
            'team1_score': match.team1_score,
            'team2_score': match.team2_score,
            'overtime': getattr(match, 'overtime', False),
            'shootout': getattr(match, 'shootout', False),
            'last_updated': match.updated_at.isoformat() if hasattr(match, 'updated_at') else None
        }
        
        # Aggiungi statistiche giocatori
        if match.team1:
            for player in match.team1.players:
                stats = PlayerMatchStats.query.filter_by(player_id=player.id, match_id=match.id).first()
                if stats:
                    current_data[f'player_{player.id}_goals'] = stats.goals
                    current_data[f'player_{player.id}_assists'] = stats.assists
                    current_data[f'player_{player.id}_penalties'] = stats.penalties
                    current_data[f'player_{player.id}_jersey_number'] = stats.jersey_number
                    current_data[f'player_{player.id}_goal_times'] = stats.goal_times
                    current_data[f'player_{player.id}_assist_times'] = stats.assist_times
                    current_data[f'player_{player.id}_penalty_times'] = stats.penalty_times
                    current_data[f'player_{player.id}_penalty_durations'] = stats.penalty_durations
                    
                    if stats.is_best_player_team1:
                        current_data['best_player_team1'] = str(player.id)
        
        if match.team2:
            for player in match.team2.players:
                stats = PlayerMatchStats.query.filter_by(player_id=player.id, match_id=match.id).first()
                if stats:
                    current_data[f'player_{player.id}_goals'] = stats.goals
                    current_data[f'player_{player.id}_assists'] = stats.assists
                    current_data[f'player_{player.id}_penalties'] = stats.penalties
                    current_data[f'player_{player.id}_jersey_number'] = stats.jersey_number
                    current_data[f'player_{player.id}_goal_times'] = stats.goal_times
                    current_data[f'player_{player.id}_assist_times'] = stats.assist_times
                    current_data[f'player_{player.id}_penalty_times'] = stats.penalty_times
                    current_data[f'player_{player.id}_penalty_durations'] = stats.penalty_durations
                    
                    if stats.is_best_player_team2:
                        current_data['best_player_team2'] = str(player.id)
        
        return jsonify({'success': True, 'data': current_data})
        
    except Exception as e:
        print(f"❌ Errore get current data: {e}")
        return jsonify({'success': False, 'message': str(e)})


        

@app.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """Pagina delle configurazioni del torneo."""
    try:
        settings = TournamentSettings.get_settings()
        if not settings:
            # Se non ci sono settings, mostra una pagina di inizializzazione
            return render_template('settings_init.html')
        return render_template('settings.html', settings=settings)
    except Exception as e:
        flash(f'❌ Errore nel caricamento delle configurazioni: {str(e)}', 'danger')
        return render_template('settings_init.html')


@app.route('/settings/dates', methods=['POST'])
def update_dates():
    """Aggiorna le date del torneo."""
    try:
        settings = TournamentSettings.get_settings()
        
        # Aggiorna le date
        settings.qualification_day1 = datetime.strptime(request.form.get('qualification_day1'), '%Y-%m-%d').date()
        settings.qualification_day2 = datetime.strptime(request.form.get('qualification_day2'), '%Y-%m-%d').date()
        settings.quarterfinals_ml_date = datetime.strptime(request.form.get('quarterfinals_ml_date'), '%Y-%m-%d').date()
        settings.quarterfinals_bl_date = datetime.strptime(request.form.get('quarterfinals_bl_date'), '%Y-%m-%d').date()
        settings.semifinals_ml_date = datetime.strptime(request.form.get('semifinals_ml_date'), '%Y-%m-%d').date()
        settings.semifinals_bl_date = datetime.strptime(request.form.get('semifinals_bl_date'), '%Y-%m-%d').date()
        settings.finals_date = datetime.strptime(request.form.get('finals_date'), '%Y-%m-%d').date()
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Date del torneo aggiornate con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f' Errore nell\'aggiornamento delle date: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))






@app.route('/settings/times', methods=['POST'])
def update_times():
    """Aggiorna gli orari del torneo e applica automaticamente al calendario."""
    try:
        import json
        settings = TournamentSettings.get_settings()
        
        # Qualificazioni - ottieni gli orari dal form
        qual_times = []
        i = 0
        while f'qual_time_{i}' in request.form:
            time_str = request.form.get(f'qual_time_{i}')
            if time_str:
                qual_times.append(time_str)
            i += 1
        
        # Playoff
        playoff_times = []
        i = 0
        while f'playoff_time_{i}' in request.form:
            time_str = request.form.get(f'playoff_time_{i}')
            if time_str:
                playoff_times.append(time_str)
            i += 1
        
        # Finali ML
        final_ml_times = []
        i = 0
        while f'final_ml_time_{i}' in request.form:
            time_str = request.form.get(f'final_ml_time_{i}')
            if time_str:
                final_ml_times.append(time_str)
            i += 1
        
        # Finali BL
        final_bl_times = []
        i = 0
        while f'final_bl_time_{i}' in request.form:
            time_str = request.form.get(f'final_bl_time_{i}')
            if time_str:
                final_bl_times.append(time_str)
            i += 1
        
        # Salva nei settings
        settings.qualification_times = json.dumps(qual_times)
        settings.playoff_times = json.dumps(playoff_times)
        settings.final_times_ml = json.dumps(final_ml_times)
        settings.final_times_bl = json.dumps(final_bl_times)
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        # AUTO-AGGIORNA IL CALENDARIO ESISTENTE (se richiesto)
        auto_update_calendar = request.form.get('auto_update_calendar') == 'on'
        
        if auto_update_calendar:
            # Applica automaticamente gli orari al calendario esistente
            updated_matches = update_existing_schedule_times(settings)
            # IMPORTANTE: Commit esplicito per le partite
            db.session.commit()
            flash(f'✅ Orari del torneo aggiornati e applicati a {updated_matches} partite del calendario!', 'success')
        else:
            flash('✅ Orari del torneo aggiornati con successo! Usa il pulsante "Applica al Calendario" per aggiornare le partite esistenti.', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore nell\'aggiornamento degli orari: {str(e)}', 'danger')
        import traceback
        print(f"Errore dettagliato update_times: {traceback.format_exc()}")
    
    return redirect(url_for('settings'))


# AGGIORNARE anche la route update_schedule_times per includere il commit:

@app.route('/settings/update_schedule_times', methods=['POST'])
def update_schedule_times():
    """Aggiorna gli orari delle partite esistenti nel calendario in base ai nuovi settings."""
    try:
        settings = TournamentSettings.get_settings()
        
        if not settings:
            flash('❌ Settings non trovati. Inizializza prima le configurazioni.', 'danger')
            return redirect(url_for('settings'))
        
        # Chiama la funzione di aggiornamento
        updated_matches = update_existing_schedule_times(settings)
        
        # IMPORTANTE: Commit esplicito
        db.session.commit()
        
        if updated_matches > 0:
            flash(f'✅ Aggiornati gli orari di {updated_matches} partite nel calendario!', 'success')
        else:
            flash('ℹ️ Nessuna partita da aggiornare. Gli orari erano già corretti.', 'info')
            
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore nell\'aggiornamento degli orari del calendario: {str(e)}', 'danger')
        import traceback
        print(f"Errore dettagliato update_schedule_times: {traceback.format_exc()}")
    
    return redirect(url_for('settings'))



def update_existing_schedule_times(settings):
    """Funzione helper per aggiornare gli orari del calendario esistente."""
    import json
    
    # Ottieni gli orari dai settings
    qual_times = json.loads(settings.qualification_times) if settings.qualification_times else ["09:00", "10:30", "12:00", "13:30", "15:00", "16:30"]
    playoff_times = json.loads(settings.playoff_times) if settings.playoff_times else ["18:00", "19:30", "21:00"]
    final_ml_times = json.loads(settings.final_times_ml) if settings.final_times_ml else ["18:00", "19:30", "21:00"]
    final_bl_times = json.loads(settings.final_times_bl) if settings.final_times_bl else ["18:00", "19:30", "21:00"]
    
    updated_matches = 0
    
    # 1. AGGIORNA QUALIFICAZIONI
    qualification_matches = Match.query.filter_by(phase='group').order_by(Match.date, Match.time).all()
    matches_by_date = {}
    for match in qualification_matches:
        if match.date not in matches_by_date:
            matches_by_date[match.date] = []
        matches_by_date[match.date].append(match)
    
    for date, matches in matches_by_date.items():
        for i, match in enumerate(matches):
            if i < len(qual_times):
                try:
                    new_time = datetime.strptime(qual_times[i], '%H:%M').time()
                    if match.time != new_time:
                        match.time = new_time
                        updated_matches += 1
                except ValueError:
                    continue
    
    # 2. AGGIORNA QUARTI DI FINALE
    quarterfinal_matches = Match.query.filter_by(phase='quarterfinal').order_by(Match.date, Match.time).all()
    
    # Raggruppa per categoria (Major League vs Beer League)
    qf_ml = [m for m in quarterfinal_matches if getattr(m, 'league', None) == 'Major League']
    qf_bl = [m for m in quarterfinal_matches if getattr(m, 'league', None) == 'Beer League']
    
    # Aggiorna quarti ML
    for i, match in enumerate(qf_ml):
        if i < len(playoff_times):
            try:
                new_time = datetime.strptime(playoff_times[i], '%H:%M').time()
                if match.time != new_time:
                    match.time = new_time
                    updated_matches += 1
            except ValueError:
                continue
    
    # Aggiorna quarti BL
    for i, match in enumerate(qf_bl):
        if i < len(playoff_times):
            try:
                new_time = datetime.strptime(playoff_times[i], '%H:%M').time()
                if match.time != new_time:
                    match.time = new_time
                    updated_matches += 1
            except ValueError:
                continue
    
    # 3. AGGIORNA SEMIFINALI
    semifinal_matches = Match.query.filter_by(phase='semifinal').order_by(Match.date, Match.time).all()
    
    sf_ml = [m for m in semifinal_matches if getattr(m, 'league', None) == 'Major League']
    sf_bl = [m for m in semifinal_matches if getattr(m, 'league', None) == 'Beer League']
    
    # Aggiorna semifinali ML
    for i, match in enumerate(sf_ml):
        if i < len(playoff_times):
            try:
                new_time = datetime.strptime(playoff_times[i], '%H:%M').time()
                if match.time != new_time:
                    match.time = new_time
                    updated_matches += 1
            except ValueError:
                continue
    
    # Aggiorna semifinali BL
    for i, match in enumerate(sf_bl):
        if i < len(playoff_times):
            try:
                new_time = datetime.strptime(playoff_times[i], '%H:%M').time()
                if match.time != new_time:
                    match.time = new_time
                    updated_matches += 1
            except ValueError:
                continue
    
    # 4. AGGIORNA FINALI
    final_matches = Match.query.filter_by(phase='final').order_by(Match.date, Match.time).all()
    
    final_ml = [m for m in final_matches if getattr(m, 'league', None) == 'Major League']
    final_bl = [m for m in final_matches if getattr(m, 'league', None) == 'Beer League']
    
    # Aggiorna finali ML
    for i, match in enumerate(final_ml):
        if i < len(final_ml_times):
            try:
                new_time = datetime.strptime(final_ml_times[i], '%H:%M').time()
                if match.time != new_time:
                    match.time = new_time
                    updated_matches += 1
            except ValueError:
                continue
    
    # Aggiorna finali BL
    for i, match in enumerate(final_bl):
        if i < len(final_bl_times):
            try:
                new_time = datetime.strptime(final_bl_times[i], '%H:%M').time()
                if match.time != new_time:
                    match.time = new_time
                    updated_matches += 1
            except ValueError:
                continue
    
    # 5. AGGIORNA TERZI/QUARTI POSTI (se esistono)
    third_place_matches = Match.query.filter_by(phase='third_place').order_by(Match.date, Match.time).all()
    
    tp_ml = [m for m in third_place_matches if getattr(m, 'league', None) == 'Major League']
    tp_bl = [m for m in third_place_matches if getattr(m, 'league', None) == 'Beer League']
    
    # Aggiorna terzi posti ML
    for i, match in enumerate(tp_ml):
        if i < len(final_ml_times):
            try:
                new_time = datetime.strptime(final_ml_times[i], '%H:%M').time()
                if match.time != new_time:
                    match.time = new_time
                    updated_matches += 1
            except ValueError:
                continue
    
    # Aggiorna terzi posti BL
    for i, match in enumerate(tp_bl):
        if i < len(final_bl_times):
            try:
                new_time = datetime.strptime(final_bl_times[i], '%H:%M').time()
                if match.time != new_time:
                    match.time = new_time
                    updated_matches += 1
            except ValueError:
                continue
    
    return updated_matches


# AGGIUNGERE TEMPORANEAMENTE in app.py per fare debug

@app.route('/debug_times')
def debug_times():
    """Route di debug per verificare gli orari."""
    import json
    
    # 1. Controlla i settings
    settings = TournamentSettings.get_settings()
    if settings:
        print("=== SETTINGS ORARI ===")
        print(f"qualification_times (raw): {settings.qualification_times}")
        print(f"playoff_times (raw): {settings.playoff_times}")
        print(f"final_times_ml (raw): {settings.final_times_ml}")
        print(f"final_times_bl (raw): {settings.final_times_bl}")
        
        if settings.qualification_times:
            qual_times = json.loads(settings.qualification_times)
            print(f"qualification_times (parsed): {qual_times}")
        
        if settings.playoff_times:
            playoff_times = json.loads(settings.playoff_times)
            print(f"playoff_times (parsed): {playoff_times}")
    else:
        print("❌ NESSUN SETTINGS TROVATO")
    
    # 2. Controlla alcune partite di esempio
    print("\n=== PARTITE ATTUALI ===")
    
    # Qualificazioni
    qual_matches = Match.query.filter_by(phase='group').order_by(Match.date, Match.time).limit(5).all()
    print("Prime 5 qualificazioni:")
    for match in qual_matches:
        print(f"  Partita {match.id}: {match.time} - {match.get_team1_display_name()} vs {match.get_team2_display_name()}")
    
    # Playoff
    playoff_matches = Match.query.filter_by(phase='quarterfinal').order_by(Match.date, Match.time).limit(3).all()
    print("Prime 3 quarti di finale:")
    for match in playoff_matches:
        print(f"  Partita {match.id}: {match.time} - {match.get_team1_display_name()} vs {match.get_team2_display_name()}")
    
    # 3. Simula l'aggiornamento senza salvare
    if settings:
        print("\n=== SIMULAZIONE AGGIORNAMENTO ===")
        try:
            qual_times = json.loads(settings.qualification_times) if settings.qualification_times else []
            print(f"Orari qualificazioni che dovrebbero essere applicati: {qual_times}")
            
            for i, match in enumerate(qual_matches):
                if i < len(qual_times):
                    try:
                        new_time = datetime.strptime(qual_times[i], '%H:%M').time()
                        print(f"  Partita {match.id}: {match.time} -> {new_time} (cambio: {match.time != new_time})")
                    except ValueError as e:
                        print(f"  Errore parsing orario '{qual_times[i]}': {e}")
        except Exception as e:
            print(f"❌ Errore simulazione: {e}")
    
    flash('Debug stampato nella console. Controlla il terminale/log.', 'info')
    return redirect(url_for('settings'))

# AGGIUNGERE ANCHE questa route per testare l'aggiornamento manuale

@app.route('/test_update_times')
def test_update_times():
    """Test manual di aggiornamento orari."""
    try:
        settings = TournamentSettings.get_settings()
        if not settings:
            flash('❌ Settings non trovati', 'danger')
            return redirect(url_for('settings'))
        
        # Chiama la funzione di aggiornamento
        updated_count = update_existing_schedule_times(settings)
        
        # IMPORTANTE: Commit esplicito
        db.session.commit()
        
        flash(f'✅ Test completato! Aggiornate {updated_count} partite.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore nel test: {str(e)}', 'danger')
        import traceback
        print(f"Errore dettagliato: {traceback.format_exc()}")
    
    return redirect(url_for('schedule'))

@app.route('/settings/teams', methods=['POST'])
def update_team_settings():
    """Aggiorna le configurazioni delle squadre."""
    try:
        settings = TournamentSettings.get_settings()
        
        settings.max_teams = int(request.form.get('max_teams', 16))
        settings.teams_per_group = int(request.form.get('teams_per_group', 4))
        settings.max_registration_points = int(request.form.get('max_registration_points', 20))
        settings.min_players_per_team = int(request.form.get('min_players_per_team', 8))
        settings.max_players_per_team = int(request.form.get('max_players_per_team', 15))
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Configurazioni squadre aggiornate con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'aggiornamento configurazioni squadre: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/settings/points', methods=['POST'])
def update_points_system():
    """Aggiorna il sistema punti."""
    try:
        settings = TournamentSettings.get_settings()
        
        settings.points_win = int(request.form.get('points_win', 3))
        settings.points_draw = int(request.form.get('points_draw', 1))
        settings.points_loss = int(request.form.get('points_loss', 0))
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Sistema punti aggiornato con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'aggiornamento sistema punti: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/settings/playoff', methods=['POST'])
def update_playoff_system():
    """Aggiorna il sistema playoff."""
    try:
        import json
        settings = TournamentSettings.get_settings()
        
        # Aggiorna accoppiamenti quarti di finale
        matchups = []
        for i in range(4):
            team1 = request.form.get(f'qf_team1_{i}')
            team2 = request.form.get(f'qf_team2_{i}')
            if team1 and team2:
                matchups.append({
                    "position": i + 1,
                    "team1": team1,
                    "team2": team2
                })
        
        settings.quarterfinal_matchups = json.dumps(matchups)
        settings.auto_update_playoffs = 'auto_update_playoffs' in request.form
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Sistema playoff aggiornato con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'aggiornamento sistema playoff: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/settings/general', methods=['POST'])
def update_general_settings():
    """Aggiorna le configurazioni generali."""
    try:
        settings = TournamentSettings.get_settings()
        
        settings.tournament_name = request.form.get('tournament_name', settings.tournament_name)
        settings.maintenance_mode = 'maintenance_mode' in request.form
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Configurazioni generali aggiornate con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'aggiornamento configurazioni generali: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/settings/reset', methods=['POST'])
def reset_settings():
    """Reset delle configurazioni ai valori di default."""
    try:
        # Elimina configurazioni esistenti
        TournamentSettings.query.delete()
        db.session.commit()
        
        # Crea nuove configurazioni di default
        TournamentSettings.create_default()
        
        flash('Configurazioni ripristinate ai valori di default!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nel reset delle configurazioni: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))


@app.route('/fix_category_field', methods=['GET', 'POST'])
def fix_category_field():
    """Aggiorna il campo category per supportare stringhe più lunghe."""
    try:
        # Per PostgreSQL, dobbiamo alterare la colonna
        with db.engine.connect() as conn:
            conn.execute(db.text('ALTER TABLE player ALTER COLUMN category TYPE VARCHAR(100)'))
            conn.commit()
        
        return '''
        <h2>✅ Campo category aggiornato con successo!</h2>
        <p>Il campo category ora supporta fino a 100 caratteri.</p>
        <p><a href="/migrate_from_sqlite">← Riprova la migrazione</a></p>
        <p><a href="/">← Torna alla Home</a></p>
        '''
        
    except Exception as e:
        return f'''
        <h2>❌ Errore nell'aggiornamento</h2>
        <p><strong>Errore:</strong> {str(e)}</p>
        <p><a href="/">← Torna alla Home</a></p>
        '''

@app.route('/settings/migrate', methods=['POST'])
def migrate_settings():
    """Migra il database per aggiungere la tabella settings."""
    try:
        # Crea la tabella se non esiste
        db.create_all()
        
        # Assicurati che esistano configurazioni di default
        settings = TournamentSettings.get_settings()
        
        flash('Migrazione settings completata con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la migrazione: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))


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

@app.teardown_appcontext
def cleanup_db(error):
    if error:
        db.session.rollback()
    db.session.remove()

@app.errorhandler(500)
def handle_database_error(e):
    db.session.rollback()
    flash('Errore del database. Riprova.', 'error')
    return redirect(url_for('index'))


@app.route('/migrate_penalty_durations')
def migrate_penalty_durations():
    """Migrazione per aggiungere il campo penalty_durations."""
    try:
        # Verifica se la tabella PlayerMatchStats esiste
        if not db.inspect(db.engine).has_table('player_match_stats'):
            flash('❌ La tabella PlayerMatchStats non esiste.', 'danger')
            return redirect(url_for('index'))
        
        # Ottieni le colonne esistenti
        inspector = db.inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('player_match_stats')]
        
        # Aggiungi la nuova colonna se non esiste
        if 'penalty_durations' not in existing_columns:
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE player_match_stats ADD COLUMN penalty_durations TEXT'))
                    conn.commit()
                flash('✅ Colonna penalty_durations aggiunta con successo!', 'success')
            except Exception as e:
                flash(f'❌ Errore nell\'aggiungere la colonna penalty_durations: {str(e)}', 'danger')
                return redirect(url_for('index'))
        else:
            flash('ℹ️ La colonna penalty_durations è già presente.', 'info')
        
    except Exception as e:
        flash(f'❌ Errore durante la migrazione: {str(e)}', 'danger')
    
    return redirect(url_for('index'))
@app.route('/migrate_player_stats_schema', methods=['GET', 'POST'])
def migrate_player_stats_schema():
    """Migra il database per aggiungere i nuovi campi alle statistiche giocatori."""
    try:
        # Verifica se la tabella PlayerMatchStats esiste
        if not db.inspect(db.engine).has_table('player_match_stats'):
            flash('❌ La tabella PlayerMatchStats non esiste. Crea prima il database.', 'danger')
            return redirect(url_for('index'))
        
        # Lista delle nuove colonne da aggiungere
        new_columns = [
            ('goal_times', 'TEXT'),
            ('assist_times', 'TEXT'), 
            ('penalty_times', 'TEXT'),
            ('jersey_number', 'INTEGER')
        ]
        
        # Ottieni le colonne esistenti
        inspector = db.inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('player_match_stats')]
        
        # Aggiungi le nuove colonne se non esistono
        columns_added = []
        for column_name, column_type in new_columns:
            if column_name not in existing_columns:
                try:
                    with db.engine.connect() as conn:
                        conn.execute(db.text(f'ALTER TABLE player_match_stats ADD COLUMN {column_name} {column_type}'))
                        conn.commit()
                    columns_added.append(column_name)
                except Exception as e:
                    flash(f'❌ Errore nell\'aggiungere la colonna {column_name}: {str(e)}', 'danger')
                    return redirect(url_for('index'))
        
        if columns_added:
            flash(f'✅ Migrazione completata! Aggiunte colonne: {", ".join(columns_added)}', 'success')
        else:
            flash('ℹ️ Tutte le colonne sono già presenti nel database.', 'info')
        
        # Verifica finale
        updated_columns = [col['name'] for col in inspector.get_columns('player_match_stats')]
        flash(f'📊 Colonne attuali nella tabella: {", ".join(updated_columns)}', 'info')
        
    except Exception as e:
        flash(f'❌ Errore durante la migrazione: {str(e)}', 'danger')
    
    return redirect(url_for('index'))


# Aggiungi anche questa route per verificare lo schema attuale
@app.route('/verify_database_schema')
def verify_database_schema():
    """Verifica lo schema attuale del database."""
    try:
        inspector = db.inspect(db.engine)
        
        # Verifica tabelle esistenti
        tables = inspector.get_table_names()
        flash(f'📋 Tabelle nel database: {", ".join(tables)}', 'info')
        
        # Se esiste PlayerMatchStats, mostra le colonne
        if 'player_match_stats' in tables:
            columns = inspector.get_columns('player_match_stats')
            column_info = []
            for col in columns:
                column_info.append(f"{col['name']} ({col['type']})")
            flash(f'🔍 Colonne in player_match_stats: {", ".join(column_info)}', 'info')
        else:
            flash('⚠️ La tabella player_match_stats non esiste', 'warning')
        
    except Exception as e:
        flash(f'❌ Errore nella verifica schema: {str(e)}', 'danger')
    
    return redirect(url_for('index'))


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


# def get_tournament_dates():
#     """
#     Calcola le date del torneo per l'anno corrente.
#     Il torneo inizia sempre il sabato della seconda settimana di luglio.
#     """
#     current_year = datetime.now().year
    
#     # Trova il primo sabato di luglio
#     july_first = datetime(current_year, 7, 1)
    
#     # Calcola quanti giorni mancano al primo sabato
#     # calendar.SATURDAY = 5 (0=lunedì, 1=martedì, ..., 6=domenica)
#     days_until_saturday = (calendar.SATURDAY - july_first.weekday()) % 7
    
#     # Se il primo luglio è già sabato, days_until_saturday sarà 0
#     # Se il primo luglio è domenica, days_until_saturday sarà 6
#     first_saturday = july_first + timedelta(days=days_until_saturday)
    
#     # Il torneo inizia il sabato della SECONDA settimana (aggiungi 7 giorni)
#     tournament_start = first_saturday + timedelta(days=7)
    
#     # Calcola tutte le date del torneo
#     dates = {
#         'qualification_day1': tournament_start.date(),                    # Sabato (qualificazioni)
#         'qualification_day2': (tournament_start + timedelta(days=1)).date(),  # Domenica (qualificazioni)
#         'quarterfinals_ml': (tournament_start + timedelta(days=2)).date(),     # Lunedì (quarti ML)
#         'quarterfinals_bl': (tournament_start + timedelta(days=3)).date(),     # Martedì (quarti BL)
#         'semifinals_ml': (tournament_start + timedelta(days=5)).date(),        # Giovedì (semi ML)
#         'semifinals_bl': (tournament_start + timedelta(days=6)).date(),        # Venerdì (semi BL)
#         'finals': (tournament_start + timedelta(days=7)).date()               # Sabato (finali)
#     }
    
#     return dates



# def get_tournament_times():
#     """
#     Restituisce gli orari standardizzati per ogni fase del torneo.
#     """
#     return {
#         'qualification_times': [
#             time(10, 0), time(10, 45), time(11, 30), time(12, 15), time(13, 00),
#             time(13, 45), time(14, 30), time(15, 15), time(16, 00), time(16, 45),
#             time(17, 30), time(18, 15)
#         ],
#         'playoff_times': [time(19, 00), time(19, 45), time(20, 30), time(21, 15)],
#         'final_times_ml': [time(12, 0), time(14, 0), time(16, 0), time(18, 0)],
#         'final_times_bl': [time(11, 0), time(13, 0), time(15, 0), time(17, 0)]
#     }


def get_tournament_dates():
    """
    Ottieni le date del torneo dalle configurazioni o calcola quelle di default.
    """
    try:
        # Solo se la tabella esiste e ci sono settings
        if db.inspect(db.engine).has_table('tournament_settings'):
            settings = TournamentSettings.query.first()
            if settings and settings.qualification_day1:
                return {
                    'qualification_day1': settings.qualification_day1,
                    'qualification_day2': settings.qualification_day2,
                    'quarterfinals_ml': settings.quarterfinals_ml_date,
                    'quarterfinals_bl': settings.quarterfinals_bl_date,
                    'semifinals_ml': settings.semifinals_ml_date,
                    'semifinals_bl': settings.semifinals_bl_date,
                    'finals': settings.finals_date
                }
    except Exception as e:
        print(f"Errore nel recupero date da settings: {e}")
    
    # Fallback alle date calcolate automaticamente
    current_year = datetime.now().year
    july_first = datetime(current_year, 7, 1)
    days_until_saturday = (calendar.SATURDAY - july_first.weekday()) % 7
    first_saturday = july_first + timedelta(days=days_until_saturday)
    tournament_start = first_saturday + timedelta(days=7)
    
    return {
        'qualification_day1': tournament_start.date(),
        'qualification_day2': (tournament_start + timedelta(days=1)).date(),
        'quarterfinals_ml': (tournament_start + timedelta(days=2)).date(),
        'quarterfinals_bl': (tournament_start + timedelta(days=3)).date(),
        'semifinals_ml': (tournament_start + timedelta(days=5)).date(),
        'semifinals_bl': (tournament_start + timedelta(days=6)).date(),
        'finals': (tournament_start + timedelta(days=7)).date()
    }

def get_tournament_times():
    """
    Ottieni gli orari del torneo dalle configurazioni o usa quelli di default.
    """
    try:
        # Solo se la tabella esiste e ci sono settings
        if db.inspect(db.engine).has_table('tournament_settings'):
            settings = TournamentSettings.query.first()
            if settings and settings.qualification_times:
                import json
                return {
                    'qualification_times': settings.get_qualification_times_list(),
                    'playoff_times': settings.get_playoff_times_list(),
                    'final_times_ml': [datetime.strptime(t, '%H:%M').time() for t in json.loads(settings.final_times_ml)] if settings.final_times_ml else [],
                    'final_times_bl': [datetime.strptime(t, '%H:%M').time() for t in json.loads(settings.final_times_bl)] if settings.final_times_bl else []
                }
    except Exception as e:
        print(f"Errore nel recupero orari da settings: {e}")
    
    # Fallback agli orari di default
    return {
        'qualification_times': [
            time(10, 0), time(10, 45), time(11, 30), time(12, 15), time(13, 00),
            time(13, 45), time(14, 30), time(15, 15), time(16, 00), time(16, 45),
            time(17, 30), time(18, 15)
        ],
        'playoff_times': [time(19, 00), time(19, 45), time(20, 30), time(21, 15)],
        'final_times_ml': [time(13, 0), time(15, 0), time(17, 0), time(19, 0)],
        'final_times_bl': [time(12, 0), time(14, 0), time(16, 0), time(18, 0)]
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

@app.template_filter('from_json')
def from_json_filter(value):
    """Converte una stringa JSON in oggetto Python."""
    import json
    try:
        if value:
            return json.loads(value)
    except:
        pass
    return []


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
@login_required
@admin_required 
def teams():
    # Ordina le squadre per girone e poi per group_order
    teams = Team.query.order_by(Team.group.nulls_last(), Team.group_order, Team.name).all()
    team_count = Team.query.count()
    max_teams = 16
    return render_template('teams.html', teams=teams, team_count=team_count, max_teams=max_teams)


@app.route('/add_team', methods=['POST'])
@login_required
@admin_required 
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
        
        # Crea il nuovo giocatore
        player = Player(name=player_name, team=team, is_registered=is_registered, category=category)
        db.session.add(player)
        db.session.commit()  # Commit per ottenere l'ID del giocatore
        
        # NUOVA LOGICA: Rimuovi automaticamente il giocatore dalle partite già completate
        completed_matches = Match.query.filter(
            ((Match.team1_id == team.id) | (Match.team2_id == team.id)),
            Match.team1_score.isnot(None),
            Match.team2_score.isnot(None)
        ).all()
        
        if completed_matches:
            matches_removed_from = 0
            
            # Verifica che la tabella PlayerMatchStats esista
            if db.inspect(db.engine).has_table('player_match_stats'):
                for match in completed_matches:
                    # Trova o crea le statistiche per questo giocatore in questa partita
                    stats = PlayerMatchStats.query.filter_by(
                        player_id=player.id,
                        match_id=match.id
                    ).first()
                    
                    if not stats:
                        # Crea nuove statistiche per questa partita, ma marcate come rimosse
                        stats = PlayerMatchStats(
                            player_id=player.id,
                            match_id=match.id,
                            goals=0,
                            assists=0,
                            penalties=0,
                            is_removed=True  # Segna come rimosso automaticamente
                        )
                        db.session.add(stats)
                        matches_removed_from += 1
                    else:
                        # Se esistono già statistiche, marcale come rimosse
                        if not stats.is_removed:
                            stats.is_removed = True
                            matches_removed_from += 1
                
                db.session.commit()
                
                if matches_removed_from > 0:
                    flash(f'✅ {player_name} aggiunto a {team.name}', 'success')
                    flash(f'🔄 Giocatore automaticamente rimosso da {matches_removed_from} partite già completate', 'info')
                else:
                    flash(f'✅ {player_name} aggiunto a {team.name}', 'success')
            else:
                flash(f'✅ {player_name} aggiunto a {team.name}', 'success')
                flash('⚠️ Sistema statistiche non disponibile - controlla manualmente le partite', 'warning')
        else:
            flash(f'✅ {player_name} aggiunto a {team.name}', 'success')
        
        # Check if team exceeds registration points limit
        if team.player_points_total > 20:
            flash('⚠️ Attenzione: La squadra supera il limite di 20 punti tesseramento!', 'warning')
    return render_template('team_detail.html', team=team)



@app.route('/team/<int:team_id>/fix_existing_players', methods=['POST'])
def fix_existing_players_in_completed_matches(team_id):
    """
    Funzione di utilità per sistemare giocatori esistenti che potrebbero 
    essere presenti in partite precedenti alla loro aggiunta al team.
    """
    team = Team.query.get_or_404(team_id)
    
    if not db.inspect(db.engine).has_table('player_match_stats'):
        flash('❌ Sistema statistiche non disponibile', 'danger')
        return redirect(url_for('team_detail', team_id=team_id))
    
    # Trova tutte le partite completate di questa squadra
    completed_matches = Match.query.filter(
        ((Match.team1_id == team.id) | (Match.team2_id == team.id)),
        Match.team1_score.isnot(None),
        Match.team2_score.isnot(None)
    ).all()
    
    if not completed_matches:
        flash('ℹ️ Nessuna partita completata trovata per questa squadra', 'info')
        return redirect(url_for('team_detail', team_id=team_id))
    
    # Mostra una pagina di conferma con l'elenco dei giocatori e delle partite
    players_with_stats = []
    
    for player in team.players:
        player_matches = []
        for match in completed_matches:
            stats = PlayerMatchStats.query.filter_by(
                player_id=player.id,
                match_id=match.id
            ).first()
            
            if stats and not stats.is_removed:
                opponent = match.team1 if match.team2_id == team.id else match.team2
                player_matches.append({
                    'match': match,
                    'opponent': opponent.name if opponent else 'Sconosciuto',
                    'date': match.date,
                    'has_stats': stats.goals > 0 or stats.assists > 0 or stats.penalties > 0
                })
        
        if player_matches:
            players_with_stats.append({
                'player': player,
                'matches': player_matches
            })
    
    if request.form.get('confirm') == 'yes':
        # Esegui la rimozione automatica
        total_removed = 0
        for player in team.players:
            for match in completed_matches:
                stats = PlayerMatchStats.query.filter_by(
                    player_id=player.id,
                    match_id=match.id
                ).first()
                
                if stats and not stats.is_removed:
                    stats.is_removed = True
                    total_removed += 1
        
        db.session.commit()
        flash(f'✅ {total_removed} presenze rimosse da partite completate', 'success')
        return redirect(url_for('team_detail', team_id=team_id))
    
    # Mostra la pagina di conferma
    return render_template('confirm_fix_players.html', 
                         team=team, 
                         players_with_stats=players_with_stats,
                         completed_matches=completed_matches)


@app.route('/player/<int:player_id>/edit', methods=['GET', 'POST'])
def edit_player(player_id):
    """Modifica un giocatore esistente."""
    player = Player.query.get_or_404(player_id)
    
    if request.method == 'POST':
        # Ottieni i dati dal form
        new_name = request.form.get('player_name')
        is_registered = 'is_registered' in request.form
        category = request.form.get('category') if is_registered else None
        
        # Valida che il nome non sia vuoto
        if not new_name or not new_name.strip():
            flash('Il nome del giocatore non può essere vuoto', 'danger')
            return redirect(url_for('edit_player', player_id=player_id))
        
        # Salva i vecchi valori per debug
        old_name = player.name
        old_registered = player.is_registered
        old_category = player.category
        old_points = player.registration_points
        
        # Aggiorna i dati del giocatore
        player.name = new_name.strip()
        player.is_registered = is_registered
        player.category = category
        
        # Calcola i nuovi punti
        new_points = player.registration_points
        
        try:
            db.session.commit()
            
            # Messaggio di successo con dettagli
            if old_name != player.name or old_registered != is_registered or old_category != category:
                flash(f'✅ Giocatore aggiornato: {old_name} → {player.name} '
                      f'({old_points}pt → {new_points}pt)', 'success')
            else:
                flash(f'ℹ️ Nessuna modifica per {player.name}', 'info')
            
            # Controlla se la squadra supera il limite
            team_total = player.team.player_points_total
            if team_total > 20:
                flash(f'⚠️ Attenzione: {player.team.name} ora ha {team_total} punti tesseramento (limite: 20)', 'warning')
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Errore durante l\'aggiornamento: {str(e)}', 'danger')
        
        return redirect(url_for('team_detail', team_id=player.team_id))
    
    # GET request: mostra il form di modifica
    return render_template('edit_player.html', player=player)



@app.route('/player/<int:player_id>/delete', methods=['POST'])
def delete_player(player_id):
    player = Player.query.get_or_404(player_id)
    team_id = player.team_id
    player_name = player.name
    
    try:
        # Prima elimina le statistiche del giocatore se esistono
        if db.inspect(db.engine).has_table('player_match_stats'):
            stats_deleted = PlayerMatchStats.query.filter_by(player_id=player.id).count()
            PlayerMatchStats.query.filter_by(player_id=player.id).delete()
            if stats_deleted > 0:
                print(f"Eliminate {stats_deleted} statistiche per {player_name}")
        
        # Poi elimina il giocatore
        db.session.delete(player)
        db.session.commit()
        
        flash(f'🗑️ Giocatore {player_name} rimosso con successo', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante l\'eliminazione: {str(e)}', 'danger')
    
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
@login_required
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
                    {'time': time(13, 0), 'match': 'Perdente partita 33 vs Perdente partita 34 (7°/8°)'},
                    {'time': time(15, 0), 'match': 'Vincente partita 33 vs Vincente partita 34 (5°/6°)'},
                    {'time': time(17, 0), 'match': 'Perdente partita 35 vs Perdente partita 36 (3°/4°)'},
                    {'time': time(19, 0), 'match': 'Vincente partita 35 vs Vincente partita 36 (1°/2°)'},
                ],
                'BL_matches': [
                    {'time': time(12, 0), 'match': 'Perdente partita 37 vs Perdente partita 38 (7°/8°)'},
                    {'time': time(14, 0), 'match': 'Vincente partita 37 vs Vincente partita 38 (5°/6°)'},
                    {'time': time(16, 0), 'match': 'Perdente partita 39 vs Perdente partita 40 (3°/4°)'},
                    {'time': time(18, 0), 'match': 'Vincente partita 39 vs Vincente partita 40 (1°/2°)'},
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




@app.route('/match/<int:match_id>/reset', methods=['POST'])
@login_required
def reset_match(match_id):
    """Reset completo di una singola partita - cancella risultato e tutte le statistiche."""
    print(f"🔄 RESET MATCH CHIAMATO per partita {match_id}")
    
    match = Match.query.get_or_404(match_id)
    return_anchor = request.form.get('return_anchor', '')
    
    try:
        # Salva i vecchi punteggi per aggiornare le statistiche delle squadre
        old_team1_score = match.team1_score
        old_team2_score = match.team2_score
        old_overtime = getattr(match, 'overtime', False) or False
        old_shootout = getattr(match, 'shootout', False) or False
        
        print(f"📊 Vecchi punteggi: {old_team1_score}-{old_team2_score}, OT: {old_overtime}, SO: {old_shootout}")
        
        # 2. PRIMA reset statistiche squadre (solo se c'erano dei risultati)
        if old_team1_score is not None and old_team2_score is not None and match.team1 and match.team2:
            print("🔄 Resettando statistiche squadre...")
            
            # Assicurati che le statistiche delle squadre siano inizializzate
            team1 = match.team1
            team2 = match.team2
            
            # Inizializza campi None con 0
            team1.goals_for = team1.goals_for or 0
            team1.goals_against = team1.goals_against or 0
            team1.wins = team1.wins or 0
            team1.losses = team1.losses or 0
            team1.draws = team1.draws or 0
            team1.points = team1.points or 0
            
            team2.goals_for = team2.goals_for or 0
            team2.goals_against = team2.goals_against or 0
            team2.wins = team2.wins or 0
            team2.losses = team2.losses or 0
            team2.draws = team2.draws or 0
            team2.points = team2.points or 0
            
            # Sottrai i vecchi valori dalle statistiche
            team1.goals_for -= old_team1_score
            team1.goals_against -= old_team2_score
            team2.goals_for -= old_team2_score
            team2.goals_against -= old_team1_score
            
            # Calcola e sottrai i vecchi punti usando il sistema hockey
            # Crea match temporaneo con i vecchi valori per calcolare i punti da sottrarre
            old_match = type('OldMatch', (), {
                'team1_score': old_team1_score,
                'team2_score': old_team2_score,
                'overtime': old_overtime,
                'shootout': old_shootout,
                'is_completed': True,
                'winner': team1 if old_team1_score > old_team2_score else (team2 if old_team2_score > old_team1_score else None),
                'is_regulation_time': not (old_overtime or old_shootout),
                'is_overtime_shootout': old_overtime or old_shootout
            })()
            
            # Funzione per calcolare punti (copia da Match.get_points_for_team)
            def get_old_points_for_team(team):
                if old_team1_score == old_team2_score:
                    return 1  # Pareggio
                
                is_winner = (team == team1 and old_team1_score > old_team2_score) or (team == team2 and old_team2_score > old_team1_score)
                is_loser = not is_winner and old_team1_score != old_team2_score
                
                if is_winner:
                    if not (old_overtime or old_shootout):
                        return 3  # Vittoria nei tempi regolamentari
                    else:
                        return 2  # Vittoria overtime/rigori
                elif is_loser:
                    if old_overtime or old_shootout:
                        return 1  # Sconfitta overtime/rigori
                    else:
                        return 0  # Sconfitta nei tempi regolamentari
                else:
                    return 1  # Pareggio
            
            # Sottrai i vecchi punti
            old_team1_points = get_old_points_for_team(team1)
            old_team2_points = get_old_points_for_team(team2)
            team1.points -= old_team1_points
            team2.points -= old_team2_points
            
            # Aggiorna record vittorie/sconfitte/pareggi (sottrai vecchi)
            if old_team1_score > old_team2_score:
                team1.wins -= 1
                team2.losses -= 1
            elif old_team2_score > old_team1_score:
                team2.wins -= 1
                team1.losses -= 1
            else:
                team1.draws -= 1
                team2.draws -= 1
            
            print(f"Team1 ({team1.name}): punti {team1.points}, gol {team1.goals_for}-{team1.goals_against}")
            print(f"Team2 ({team2.name}): punti {team2.points}, gol {team2.goals_for}-{team2.goals_against}")
        
        # 1. Reset risultato della partita (DOPO aver aggiornato le statistiche)
        match.team1_score = None
        match.team2_score = None
        if hasattr(match, 'overtime'):
            match.overtime = False
        if hasattr(match, 'shootout'):
            match.shootout = False
        
        # 3. Elimina tutte le statistiche dei giocatori per questa partita
        stats_deleted = 0
        try:
            if db.inspect(db.engine).has_table('player_match_stats'):
                stats_deleted = PlayerMatchStats.query.filter_by(match_id=match_id).count()
                PlayerMatchStats.query.filter_by(match_id=match_id).delete()
                print(f"🗑️ Eliminate {stats_deleted} statistiche giocatori per partita {match_id}")
        except Exception as e:
            print(f"⚠️ Errore eliminazione statistiche giocatori: {e}")
        
        db.session.commit()
        
        # Messaggio di successo
        match_description = f"{match.get_team1_display_name()} vs {match.get_team2_display_name()}"
        success_msg = f'Partita "{match_description}" resettata completamente!'
        if stats_deleted > 0:
            success_msg += f' Eliminate {stats_deleted} statistiche giocatori.'
        
        flash(success_msg, 'success')
        print(f"Reset partita {match_id} completato con successo")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ ERRORE reset partita: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'❌ Errore durante il reset della partita: {str(e)}', 'danger')
    
    # Torna alla pagina corretta
    if return_anchor:
        return redirect(url_for('match_detail', match_id=match_id) + f'?return_anchor={return_anchor}')
    else:
        return redirect(url_for('match_detail', match_id=match_id))


@app.route('/match/<int:match_id>', methods=['GET', 'POST'])
@login_required
def match_detail(match_id):
    match = Match.query.get_or_404(match_id)
    return_anchor = request.args.get('return_anchor', '')
   
    if request.method == 'POST':
        # SALVA TUTTO IN UN COLPO SOLO: RISULTATO + STATISTICHE + MIGLIORI GIOCATORI
        
        # 1. SALVA RISULTATO (se fornito)
        team1_score_str = request.form.get('team1_score')
        team2_score_str = request.form.get('team2_score')
        
        if team1_score_str and team2_score_str:
            old_team1_score = match.team1_score
            old_team2_score = match.team2_score
            old_overtime = getattr(match, 'overtime', False)
            old_shootout = getattr(match, 'shootout', False)
            
            match.team1_score = int(team1_score_str)
            match.team2_score = int(team2_score_str)
            
            # Gestione overtime/shootout con validazione regole
            rules = match.get_allowed_overtime_rules()
            
            if hasattr(match, 'overtime'):
                overtime_requested = request.form.get('overtime') == 'on'
                if overtime_requested and not rules['allow_overtime']:
                    flash(f'⚠️ Overtime non permesso in {match.phase}! {rules["description"]}', 'warning')
                    overtime_requested = False
                match.overtime = overtime_requested
            
            if hasattr(match, 'shootout'):
                shootout_requested = request.form.get('shootout') == 'on'
                if shootout_requested and not rules['allow_shootout']:
                    flash(f'⚠️ Rigori non permessi in {match.phase}! {rules["description"]}', 'warning')
                    shootout_requested = False
                match.shootout = shootout_requested
            
            # Validazione finale
            is_valid, error_msg = validate_match_overtime_rules(match)
            if not is_valid:
                flash(f'❌ {error_msg}', 'error')
                return redirect(url_for('match_detail', match_id=match_id))
            
            update_team_stats(match, old_team1_score, old_team2_score, old_overtime, old_shootout)
        
        # 2. SALVA STATISTICHE GIOCATORI + MIGLIORI GIOCATORI
        try:
            # Assicurati che la tabella PlayerMatchStats esista
            if not db.inspect(db.engine).has_table('player_match_stats'):
                flash('Errore: Sistema statistiche per partita non disponibile', 'danger')
                return redirect(url_for('match_detail', match_id=match_id))
            
            # Ottieni tutti i giocatori di entrambe le squadre
            all_players = []
            team1_players = []
            team2_players = []
            
            if match.team1:
                team1_players = list(match.team1.players)
                all_players.extend(team1_players)
            if match.team2:
                team2_players = list(match.team2.players)
                all_players.extend(team2_players)
            
            # Ottieni i migliori giocatori selezionati
            best_player_team1_id = request.form.get('best_player_team1')
            best_player_team2_id = request.form.get('best_player_team2')
            
            # Aggiorna le statistiche per tutti i giocatori
            for player in all_players:
                print(f"🔄 Aggiornamento statistiche per giocatore {player.name} (ID: {player.id})")
                # Leggi i valori base dal form
                goals = int(request.form.get(f'player_{player.id}_goals', 0))
                assists = int(request.form.get(f'player_{player.id}_assists', 0))
                
                # NUOVO: Leggi il numero di maglia
                jersey_number = request.form.get(f'player_{player.id}_jersey_number')
                jersey_number = int(jersey_number) if jersey_number and jersey_number.strip() else None
                
                # NUOVO: Leggi i tempi delle azioni
                goal_times_str = request.form.get(f'player_{player.id}_goal_times', '').strip()
                assist_times_str = request.form.get(f'player_{player.id}_assist_times', '').strip()
                
                # === NUOVA GESTIONE PENALITÀ CON DURATA ===
                penalty_times_str = request.form.get(f'player_{player.id}_penalty_times', '').strip()
                penalty_durations_str = request.form.get(f'player_{player.id}_penalty_durations', '').strip()
                total_penalty_duration = float(request.form.get(f'player_{player.id}_penalties', 0) or 0)
                
                # Converte i tempi e le durate in liste
                penalty_times = []
                if penalty_times_str:
                    try:
                        penalty_times = [int(t.strip()) for t in penalty_times_str.split(',') if t.strip().isdigit()]
                    except:
                        penalty_times = []
                
                penalty_durations = []
                if penalty_durations_str:
                    try:
                        penalty_durations = [float(d.strip()) for d in penalty_durations_str.split(',') if d.strip()]
                    except:
                        penalty_durations = []
                
                # Validazione: tempi e durate devono essere dello stesso numero
                if len(penalty_times) != len(penalty_durations) and (penalty_times or penalty_durations):
                    flash(f'Errore: {player.name} ha {len(penalty_times)} tempi penalità ma {len(penalty_durations)} durate', 'danger')
                    continue
                
                # Converte altri tempi in liste di interi
                goal_times = []
                if goal_times_str:
                    try:
                        goal_times = [int(t.strip()) for t in goal_times_str.split(',') if t.strip().isdigit()]
                    except:
                        goal_times = []
                
                assist_times = []
                if assist_times_str:
                    try:
                        assist_times = [int(t.strip()) for t in assist_times_str.split(',') if t.strip().isdigit()]
                    except:
                        assist_times = []
                
                # Validazioni esistenti per gol e assist
                if len(goal_times) != goals and goals > 0:
                    flash(f'Attenzione: {player.name} ha {goals} gol ma solo {len(goal_times)} tempi specificati', 'warning')
                if len(assist_times) != assists and assists > 0:
                    flash(f'Attenzione: {player.name} ha {assists} assist ma solo {len(assist_times)} tempi specificati', 'warning')
                
                # Determina se è il miglior giocatore
                is_best_team1 = str(player.id) == best_player_team1_id
                is_best_team2 = str(player.id) == best_player_team2_id
                
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
                        penalties=total_penalty_duration,  # ORA CONTIENE LA DURATA TOTALE
                        jersey_number=jersey_number,
                        goal_times=','.join(map(str, goal_times)) if goal_times else None,
                        assist_times=','.join(map(str, assist_times)) if assist_times else None,
                        penalty_times=','.join(map(str, penalty_times)) if penalty_times else None,
                        penalty_durations=','.join(map(str, penalty_durations)) if penalty_durations else None,  # NUOVO CAMPO
                        is_best_player_team1=is_best_team1,
                        is_best_player_team2=is_best_team2,
                        is_removed= player.is_removed if hasattr(player, 'is_removed') else False
                    )
                    db.session.add(stats)
                else:
                    # Aggiorna le statistiche esistenti per questa partita
                    stats.goals = goals
                    stats.assists = assists
                    stats.penalties = total_penalty_duration  # ORA CONTIENE LA DURATA TOTALE
                    stats.jersey_number = jersey_number if jersey_number else None
                    stats.goal_times = ','.join(map(str, goal_times)) if goal_times else None
                    stats.assist_times = ','.join(map(str, assist_times)) if assist_times else None
                    stats.penalty_times = ','.join(map(str, penalty_times)) if penalty_times else None
                    stats.penalty_durations = ','.join(map(str, penalty_durations)) if penalty_durations else None  # NUOVO CAMPO
                    stats.is_best_player_team1 = is_best_team1
                    stats.is_best_player_team2 = is_best_team2
                    # IMPORTANTE: Non modificare is_removed qui, mantieni il valore esistente
        
        except Exception as e:
            db.session.rollback()
            flash(f'Errore nel salvataggio statistiche: {str(e)}', 'danger')
            return redirect(url_for('match_detail', match_id=match_id))
        
        # 3. COMMITTA TUTTO
        db.session.commit()
        flash('✅ Partita salvata completamente: risultato, statistiche e migliori giocatori!', 'success')
        
        # Redirect con anchor se specificato
        if return_anchor:
            return redirect(url_for('schedule') + f'#{return_anchor}')
        else:
            return redirect(url_for('match_detail', match_id=match_id))
    
    # GET: Carica i dati per visualizzazione (aggiungi gestione per le nuove durate)
    team1_players = match.team1.players if match.team1 else []
    team2_players = match.team2.players if match.team2 else []
    
    # Crea un dizionario per le statistiche di questa partita con i NUOVI CAMPI
    match_stats = {}
    best_player_team1 = None
    best_player_team2 = None
    
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
                    'penalties': stats.penalties,  # Ora contiene la durata totale
                    'jersey_number': stats.jersey_number,
                    'goal_times': stats.goal_times,
                    'assist_times': stats.assist_times,
                    'penalty_times': stats.penalty_times,
                    'penalty_durations': stats.penalty_durations,  # NUOVO CAMPO
                    'is_best_player_team1': stats.is_best_player_team1,
                    'is_best_player_team2': stats.is_best_player_team2,
                    'is_removed': stats.is_removed
                }
                
                if stats.is_best_player_team1:
                    best_player_team1 = player
                if stats.is_best_player_team2:
                    best_player_team2 = player
            else:
                match_stats[player.id] = {
                    'goals': 0,
                    'assists': 0,
                    'penalties': 0,
                    'jersey_number': None,
                    'goal_times': None,
                    'assist_times': None,
                    'penalty_times': None,
                    'penalty_durations': None,  # NUOVO CAMPO
                    'is_best_player_team1': False,
                    'is_best_player_team2': False,
                    'is_removed': False
                }
    except:
        # Fallback se la tabella non esiste
        for player in team1_players + team2_players:
            match_stats[player.id] = {
                'goals': 0,
                'assists': 0,
                'penalties': 0,
                'jersey_number': None,
                'goal_times': None,
                'assist_times': None,
                'penalty_times': None,
                'penalty_durations': None,  # NUOVO CAMPO
                'is_best_player_team1': False,
                'is_best_player_team2': False,
                'is_removed': False
            }
    
    return render_template('match_detail.html', 
                           match=match, 
                           team1_players=team1_players, 
                           team2_players=team2_players, 
                           match_stats=match_stats,
                           best_player_team1=best_player_team1,
                           best_player_team2=best_player_team2,
                           return_anchor=return_anchor)

@app.route('/match/<int:match_id>/toggle_player/<int:player_id>', methods=['POST'])
@login_required
def toggle_player_in_match(match_id, player_id):
    """Rimuove o ripristina un giocatore da una partita specifica."""
    match = Match.query.get_or_404(match_id)
    player = Player.query.get_or_404(player_id)
    print(f"🔄 Toggling player {player.name} (ID: {player_id}) in match {match_id}")
    
    try:
        # Verifica che la tabella PlayerMatchStats esista
        if not db.inspect(db.engine).has_table('player_match_stats'):
            flash('Errore: Sistema statistiche per partita non disponibile', 'danger')
            return redirect(url_for('match_detail', match_id=match_id))
        
        # Trova o crea le statistiche per questo giocatore in questa partita
        stats = PlayerMatchStats.query.filter_by(
            player_id=player_id,
            match_id=match_id
        ).first()
        
        if not stats:
            # Crea nuove statistiche per questa partita
            stats = PlayerMatchStats(
                player_id=player_id,
                match_id=match_id,
                goals=0,
                assists=0,
                penalties=0,
                is_removed=True  # Segna come rimosso
            )
            db.session.add(stats)
            action = "rimosso dalla"
        else:
            # Cambia lo stato di rimozione
            stats.is_removed = not stats.is_removed
            action = "rimosso dalla" if stats.is_removed else "ripristinato nella"
            
            # Se viene rimosso, azzera anche i best player flags
            if stats.is_removed:
                if stats.is_best_player_team1:
                    stats.is_best_player_team1 = False

                if stats.is_best_player_team2:
                    stats.is_best_player_team2 = False
       
        db.session.commit()
        flash(f'{player.name} è stato {action} partita.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nel toggle del giocatore: {str(e)}', 'danger')

    return redirect(url_for('match_detail', match_id=match_id))




@app.route('/migrate_overtime_system', methods=['POST'])
def migrate_overtime_system():
    """Migra il database per aggiungere i campi overtime e shootout."""
    try:
        # Controlla se le colonne esistono già
        inspector = db.inspect(db.engine)
        
        if db.inspect(db.engine).has_table('match'):
            columns = [col['name'] for col in inspector.get_columns('match')]
            
            migrations_needed = []
            if 'overtime' not in columns:
                migrations_needed.append('overtime')
            if 'shootout' not in columns:
                migrations_needed.append('shootout')
            
            if migrations_needed:
                # Aggiungi le colonne mancanti
                with db.engine.connect() as conn:
                    for column in migrations_needed:
                        conn.execute(db.text(f'ALTER TABLE match ADD COLUMN {column} BOOLEAN DEFAULT 0'))
                    conn.commit()
                
                flash(f'🏒 Sistema Overtime/Rigori abilitato! Aggiunte colonne: {", ".join(migrations_needed)}', 'success')
            else:
                flash('ℹ️ Sistema Overtime/Rigori già abilitato.', 'info')
        else:
            # Se la tabella non esiste, creala
            db.create_all()
            flash('🏒 Tabella Match creata con sistema Overtime/Rigori!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante la migrazione Overtime: {str(e)}', 'danger')
    
    return redirect(url_for('index'))



@app.route('/recalculate_all_points', methods=['POST'])
def recalculate_all_points():
    """Ricalcola tutti i punti delle squadre usando il nuovo sistema."""
    try:
        # Reset di tutte le statistiche delle squadre
        teams = Team.query.all()
        for team in teams:
            team.wins = 0
            team.losses = 0
            team.draws = 0
            team.goals_for = 0
            team.goals_against = 0
            team.points = 0
        
        # Ricalcola da tutte le partite completate
        completed_matches = Match.query.filter(
            Match.team1_score.isnot(None),
            Match.team2_score.isnot(None)
        ).all()
        
        for match in completed_matches:
            if match.team1 and match.team2:
                update_team_stats(match, None, None, None, None)
        
        db.session.commit()
        flash(f'🔢 Punti ricalcolati per {len(completed_matches)} partite usando il sistema hockey!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante il ricalcolo: {str(e)}', 'danger')
    
    return redirect(url_for('standings'))

def get_best_players_by_match():
    """Ottiene tutti i migliori giocatori per ogni partita."""
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            best_players = []
            
            # Query per tutti i migliori giocatori squadra 1
            team1_best = db.session.query(
                PlayerMatchStats, Player, Match
            ).join(Player).join(Match).filter(
                PlayerMatchStats.is_best_player_team1 == True
            ).all()
            
            # Query per tutti i migliori giocatori squadra 2
            team2_best = db.session.query(
                PlayerMatchStats, Player, Match
            ).join(Player).join(Match).filter(
                PlayerMatchStats.is_best_player_team2 == True
            ).all()
            
            for stats, player, match in team1_best + team2_best:
                best_players.append({
                    'player': player,
                    'match': match,
                    'team': 1 if stats.is_best_player_team1 else 2,
                    'goals': stats.goals,
                    'assists': stats.assists,
                    'total_points': stats.goals + stats.assists
                })
            
            return best_players
    except Exception as e:
        print(f"Errore nel recupero migliori giocatori: {e}")
    
    return []


def get_best_player_awards():
    """Conta quante volte ogni giocatore è stato nominato miglior giocatore."""
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            # Approccio più semplice: ottieni tutti i record MVP e conta manualmente
            
            # Query per tutti i MVP team1
            team1_mvps = db.session.query(PlayerMatchStats, Player).join(Player).filter(
                PlayerMatchStats.is_best_player_team1 == True
            ).all()
            
            # Query per tutti i MVP team2  
            team2_mvps = db.session.query(PlayerMatchStats, Player).join(Player).filter(
                PlayerMatchStats.is_best_player_team2 == True
            ).all()
            
            # Conta manualmente
            player_counts = {}
            
            # Conta MVP team1
            for stats, player in team1_mvps:
                if player.id not in player_counts:
                    player_counts[player.id] = {'player': player, 'count': 0}
                player_counts[player.id]['count'] += 1
            
            # Conta MVP team2
            for stats, player in team2_mvps:
                if player.id not in player_counts:
                    player_counts[player.id] = {'player': player, 'count': 0}
                player_counts[player.id]['count'] += 1
            
            # Converti in lista ordinata
            awards = []
            for player_id, data in player_counts.items():
                awards.append((data['player'], data['count']))
            
            # Ordina per numero di award (decrescente)
            awards.sort(key=lambda x: x[1], reverse=True)
            
            return awards
            
    except Exception as e:
        print(f"Errore nel conteggio awards: {e}")
        import traceback
        traceback.print_exc()
    
    return []


@app.route('/test_mvp_simple')
def test_mvp_simple():
    """Test semplice per contare MVP."""
    try:
        # Test diretto sui dati
        team1_mvps = PlayerMatchStats.query.filter(
            PlayerMatchStats.is_best_player_team1 == True
        ).all()
        
        team2_mvps = PlayerMatchStats.query.filter(
            PlayerMatchStats.is_best_player_team2 == True
        ).all()
        
        flash(f'🔍 MVP Team1: {len(team1_mvps)}, MVP Team2: {len(team2_mvps)}', 'info')
        
        # Test della funzione corretta
        awards = get_best_player_awards()
        flash(f'🏆 Awards trovati: {len(awards)}', 'success')
        
        for player, count in awards:
            flash(f'⭐ {player.name} ({player.team.name}): {count} MVP', 'success')
            
    except Exception as e:
        flash(f'❌ Errore: {str(e)}', 'danger')
    
    return redirect(url_for('standings'))


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
        team1_players = []
        team2_players = []
        
        if match.team1:
            team1_players = list(match.team1.players)
            all_players.extend(team1_players)
        if match.team2:
            team2_players = list(match.team2.players)
            all_players.extend(team2_players)
        
        # Ottieni i migliori giocatori selezionati
        best_player_team1_id = request.form.get('best_player_team1')
        best_player_team2_id = request.form.get('best_player_team2')
        
        # Aggiorna le statistiche per tutti i giocatori
        for player in all_players:
            # Leggi i valori base dal form
            goals = int(request.form.get(f'player_{player.id}_goals', 0))
            assists = int(request.form.get(f'player_{player.id}_assists', 0))
            penalties = int(request.form.get(f'player_{player.id}_penalties', 0))
            
            # NUOVO: Leggi il numero di maglia
            jersey_number = request.form.get(f'player_{player.id}_jersey_number')
            jersey_number = int(jersey_number) if jersey_number and jersey_number.strip() else None
            
            # NUOVO: Leggi i tempi delle azioni
            goal_times_str = request.form.get(f'player_{player.id}_goal_times', '').strip()
            assist_times_str = request.form.get(f'player_{player.id}_assist_times', '').strip()
            penalty_times_str = request.form.get(f'player_{player.id}_penalty_times', '').strip()
            
            # Converte i tempi in liste di interi
            goal_times = []
            if goal_times_str:
                try:
                    goal_times = [int(t.strip()) for t in goal_times_str.split(',') if t.strip().isdigit()]
                except:
                    goal_times = []
            
            assist_times = []
            if assist_times_str:
                try:
                    assist_times = [int(t.strip()) for t in assist_times_str.split(',') if t.strip().isdigit()]
                except:
                    assist_times = []
            
            penalty_times = []
            if penalty_times_str:
                try:
                    penalty_times = [int(t.strip()) for t in penalty_times_str.split(',') if t.strip().isdigit()]
                except:
                    penalty_times = []
            
            # Validazioni: il numero di tempi deve corrispondere al numero di azioni
            if len(goal_times) != goals and goals > 0:
                flash(f'Attenzione: {player.name} ha {goals} gol ma solo {len(goal_times)} tempi specificati', 'warning')
            if len(assist_times) != assists and assists > 0:
                flash(f'Attenzione: {player.name} ha {assists} assist ma solo {len(assist_times)} tempi specificati', 'warning')
            if len(penalty_times) != penalties and penalties > 0:
                flash(f'Attenzione: {player.name} ha {penalties} penalità ma solo {len(penalty_times)} tempi specificati', 'warning')
            
            # Determina se è il miglior giocatore della sua squadra
            is_best_team1 = (str(player.id) == best_player_team1_id and player in team1_players)
            is_best_team2 = (str(player.id) == best_player_team2_id and player in team2_players)
            
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
                    penalties=penalties,
                    jersey_number=jersey_number,
                    is_best_player_team1=is_best_team1,
                    is_best_player_team2=is_best_team2
                )
                db.session.add(stats)
            else:
                # Aggiorna le statistiche esistenti per questa partita
                stats.goals = goals
                stats.assists = assists
                stats.penalties = penalties
                stats.jersey_number = jersey_number
                stats.is_best_player_team1 = is_best_team1
                stats.is_best_player_team2 = is_best_team2
            
            # Imposta i tempi usando i metodi helper
            stats.set_goal_times_list(goal_times)
            stats.set_assist_times_list(assist_times)
            stats.set_penalty_times_list(penalty_times)
        
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

def get_team_group_stats(team_id):
    """Calcola le statistiche di una squadra SOLO dalle partite di qualificazione (phase='group').
    Sistema punti hockey: 2 punti vittoria regolamentare, 2 punti vittoria overtime/rigori, 
    1 punto sconfitta overtime/rigori, 0 punti sconfitta regolamentare.
    """
    from sqlalchemy import func, case
    
    try:
        # Query per calcolare statistiche dalle partite di qualificazione
        group_stats = db.session.query(
            func.count(Match.id).label('games_played'),
            # Vittorie regolamentari
            func.sum(
                case(
                    (db.and_(Match.team1_id == team_id, Match.team1_score > Match.team2_score, Match.overtime == False, Match.shootout == False), 1),
                    (db.and_(Match.team2_id == team_id, Match.team2_score > Match.team1_score, Match.overtime == False, Match.shootout == False), 1),
                    else_=0
                )
            ).label('wins_regulation'),
            # Vittorie overtime/rigori
            func.sum(
                case(
                    (db.and_(Match.team1_id == team_id, Match.team1_score > Match.team2_score, db.or_(Match.overtime == True, Match.shootout == True)), 1),
                    (db.and_(Match.team2_id == team_id, Match.team2_score > Match.team1_score, db.or_(Match.overtime == True, Match.shootout == True)), 1),
                    else_=0
                )
            ).label('wins_overtime'),
            # Sconfitte overtime/rigori
            func.sum(
                case(
                    (db.and_(Match.team1_id == team_id, Match.team1_score < Match.team2_score, db.or_(Match.overtime == True, Match.shootout == True)), 1),
                    (db.and_(Match.team2_id == team_id, Match.team2_score < Match.team1_score, db.or_(Match.overtime == True, Match.shootout == True)), 1),
                    else_=0
                )
            ).label('losses_overtime'),
            # Sconfitte regolamentari
            func.sum(
                case(
                    (db.and_(Match.team1_id == team_id, Match.team1_score < Match.team2_score, Match.overtime == False, Match.shootout == False), 1),
                    (db.and_(Match.team2_id == team_id, Match.team2_score < Match.team1_score, Match.overtime == False, Match.shootout == False), 1),
                    else_=0
                )
            ).label('losses_regulation'),
            # Gol fatti
            func.sum(
                case(
                    (Match.team1_id == team_id, Match.team1_score),
                    (Match.team2_id == team_id, Match.team2_score),
                    else_=0
                )
            ).label('goals_for'),
            # Gol subiti
            func.sum(
                case(
                    (Match.team1_id == team_id, Match.team2_score),
                    (Match.team2_id == team_id, Match.team1_score),
                    else_=0
                )
            ).label('goals_against')
        ).filter(
            Match.phase == 'group',  # SOLO partite di qualificazione
            Match.team1_score.isnot(None),  # SOLO partite completate
            Match.team2_score.isnot(None),
            db.or_(Match.team1_id == team_id, Match.team2_id == team_id)
        ).first()
        
        if not group_stats:
            return {
                'games_played': 0, 'wins': 0, 'wins_overtime': 0, 'losses_overtime': 0, 'losses': 0,
                'goals_for': 0, 'goals_against': 0, 'goal_difference': 0, 'points': 0
            }
        
        # Calcola statistiche
        wins_reg = group_stats.wins_regulation or 0
        wins_ot = group_stats.wins_overtime or 0
        losses_ot = group_stats.losses_overtime or 0
        losses_reg = group_stats.losses_regulation or 0
        goals_for = group_stats.goals_for or 0
        goals_against = group_stats.goals_against or 0

        # Sistema punti hockey: 3-2-1-0
        points = (wins_reg * 3) + (wins_ot * 2) + (losses_ot * 1) + (losses_reg * 0)
        
        return {
            'games_played': group_stats.games_played or 0,
            'wins': wins_reg,   # Vittorie totali
            'wins_overtime': wins_ot,
            'losses_overtime': losses_ot,
            'losses': losses_ot , # Sconfitte totali
            'goals_for': goals_for,
            'goals_against': goals_against,
            'goal_difference': goals_for - goals_against,
            'points': points
        }
        
    except Exception as e:
        print(f"Errore calcolo statistiche girone per team {team_id}: {e}")
        return {
            'games_played': 0, 'wins': 0, 'wins_overtime': 0, 'losses_overtime': 0, 'losses': 0,
            'goals_for': 0, 'goals_against': 0, 'goal_difference': 0, 'points': 0
        }

def get_group_standings():
    """Calcola le classifiche dei gironi SOLO dalle partite di qualificazione."""
    group_standings = {}
    
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).all()
        teams_with_stats = []
        
        for team in teams:
            # Ottieni statistiche solo dalle qualificazioni
            stats = get_team_group_stats(team.id)
            
            # Aggiungi le statistiche temporanee al team
            team.group_games_played = stats['games_played']
            team.group_wins = stats['wins']
            team.group_wins_overtime = stats['wins_overtime']
            team.group_losses_overtime = stats['losses_overtime']
            team.group_losses = stats['losses']
            team.group_goals_for = stats['goals_for']
            team.group_goals_against = stats['goals_against']
            team.group_goal_difference = stats['goal_difference']
            team.group_points = stats['points']
            
            teams_with_stats.append(team)
        
        # Ordina le squadre per classifica gironi
        teams_with_stats.sort(key=lambda t: (
            -t.group_points,  # Punti decrescenti
            -t.group_goal_difference,  # Differenza reti decrescente
            -t.group_goals_for,  # Gol fatti decrescenti
            t.name  # Nome crescente (tiebreaker)
        ))
        
        group_standings[group] = teams_with_stats
    
    return group_standings



@app.route('/standings')
@login_required
def standings():
    """Classifiche del torneo con distinzione tra gironi e classifiche generali."""
    
    # Group stage standings - SOLO dalle qualificazioni
    group_standings = get_group_standings()
    
    # Player statistics - dalle TUTTE le partite (come prima)
    top_scorers = []
    top_assists = []
    most_penalties = []
    
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            from sqlalchemy import func
            
            # Marcatori (TUTTE le partite)
            top_scorers_query = db.session.query(
                Player,
                func.sum(PlayerMatchStats.goals).label('total_goals'),
                func.count(PlayerMatchStats.match_id).label('total_matches'),
                func.sum(PlayerMatchStats.assists).label('total_assists')
            ).join(PlayerMatchStats).filter(
                PlayerMatchStats.is_removed != True
            ).group_by(Player.id).having(
                func.sum(PlayerMatchStats.goals) > 0
            ).order_by(
                func.sum(PlayerMatchStats.goals).desc(),
                func.count(PlayerMatchStats.match_id).asc(),
                func.sum(PlayerMatchStats.assists).desc()
            ).limit(15)
            
            for player, total_goals, total_matches, total_assists in top_scorers_query:
                player.display_goals = total_goals
                player.display_matches = total_matches
                player.display_assists_for_ranking = total_assists
                top_scorers.append(player)
            
            # Assist (TUTTE le partite)
            top_assists_query = db.session.query(
                Player,
                func.sum(PlayerMatchStats.assists).label('total_assists'),
                func.count(PlayerMatchStats.match_id).label('total_matches'),
                func.sum(PlayerMatchStats.goals).label('total_goals')
            ).join(PlayerMatchStats).filter(
                PlayerMatchStats.is_removed != True
            ).group_by(Player.id).having(
                func.sum(PlayerMatchStats.assists) > 0
            ).order_by(
                func.sum(PlayerMatchStats.assists).desc(),
                func.count(PlayerMatchStats.match_id).asc(),
                func.sum(PlayerMatchStats.goals).desc()
            ).limit(15)
            
            for player, total_assists, total_matches, total_goals in top_assists_query:
                player.display_assists = total_assists
                player.display_matches = total_matches
                player.display_goals_for_ranking = total_goals
                top_assists.append(player)
                
    except Exception as e:
        print(f"Errore nel caricamento statistiche giocatori: {e}")
    
    # MVP Awards, Fair Play, ecc. (come prima)
    best_player_awards = get_best_player_awards()
    fair_play_ranking = get_fair_play_ranking()
    
    # Final Rankings
    has_final_rankings = False
    final_rankings = None
    try:
        if db.inspect(db.engine).has_table('final_ranking'):
            final_rankings = FinalRanking.query.order_by(FinalRanking.final_position).all()
            selections = AllStarTeam.query.all()
    
            has_final_rankings = final_rankings is not None and len(final_rankings) > 0
    except Exception as e:
        print(f"Errore nel caricamento classifiche finali: {e}")
    
    # All Star Team data
    all_star_data = {
        'Tesserati': {
            'Portiere': None,
            'Difensore_1': None,
            'Difensore_2': None,
            'Attaccante_1': None,
            'Attaccante_2': None
        },
        'Non Tesserati': {
            'Portiere': None,
            'Difensore_1': None,
            'Difensore_2': None,
            'Attaccante_1': None,
            'Attaccante_2': None
        }
    }
    
    try:
        if db.inspect(db.engine).has_table('all_star_team'):
            selections = AllStarTeam.query.all()
            for selection in selections:
                category = selection.category  
                position = selection.position
                if position in all_star_data[category]:
                    # Converti il Player in dizionario per la serializzazione JSON
                    all_star_data[category][position] = {
                        'id': selection.player.id,
                        'name': selection.player.name,
                        'team': {
                            'id': selection.player.team.id,
                            'name': selection.player.team.name
                        }
                    }
    except Exception as e:
        print(f"Errore nel caricamento All Star Team: {e}")
    
    # Teams per dropdown
    teams = Team.query.order_by(Team.name).all()
    
    return render_template('standings.html', 
                           group_standings=group_standings,
                           top_scorers=top_scorers,
                           top_assists=top_assists,
                           most_penalties=most_penalties,
                           best_player_awards=best_player_awards,
                           fair_play_ranking=fair_play_ranking,
                           has_final_rankings=has_final_rankings,
                           final_rankings=final_rankings,
                           teams=teams,
                           all_star_data=all_star_data)


@app.route('/migrate_all_star_team', methods=['POST'])
def migrate_all_star_team():
    """Migra il database per aggiungere la tabella all_star_team."""
    try:
        # Crea tutte le tabelle (inclusa all_star_team se non esiste)
        db.create_all()
        flash('⭐ Tabella All Star Team creata con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante la migrazione All Star Team: {str(e)}', 'danger')
    
    return redirect(url_for('standings'))



@app.route('/migrate_add_is_removed', methods=['GET', 'POST'])
@login_required
def migrate_add_is_removed():
    """Aggiunge la colonna is_removed alla tabella PlayerMatchStats."""
    
    if request.method == 'GET':
        # Mostra una pagina di conferma per la migrazione
        return '''
        <div style="max-width: 600px; margin: 50px auto; padding: 20px; font-family: Arial;">
            <h2>🔧 Migrazione Database - Campo is_removed</h2>
            <p>Questa migrazione aggiungerà la colonna <code>is_removed</code> alla tabella <code>player_match_stats</code>.</p>
            <p><strong>Cosa fa:</strong></p>
            <ul>
                <li>Aggiunge il campo per tracciare i giocatori rimossi dalle partite</li>
                <li>Imposta il valore di default a FALSE per tutti i giocatori esistenti</li>
                <li>Abilita la funzionalità X rossa per rimuovere giocatori</li>
            </ul>
            
            <form method="POST" style="margin-top: 30px;">
                <button type="submit" style="background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer;">
                    ✅ Esegui Migrazione
                </button>
                <a href="/" style="margin-left: 10px; padding: 10px 20px; background: #6c757d; color: white; text-decoration: none; border-radius: 5px;">
                    ❌ Annulla
                </a>
            </form>
        </div>
        '''
    
    # POST: Esegui la migrazione
    try:
        # Controlla se la colonna esiste già
        inspector = db.inspect(db.engine)
        if inspector.has_table('player_match_stats'):
            columns = [col['name'] for col in inspector.get_columns('player_match_stats')]
            
            if 'is_removed' not in columns:
                # Aggiungi la colonna is_removed
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE player_match_stats ADD COLUMN is_removed BOOLEAN DEFAULT 0'))
                    conn.commit()
                flash('✅ Colonna is_removed aggiunta con successo alla tabella player_match_stats!', 'success')
            else:
                flash('ℹ️ La colonna is_removed esiste già nella tabella player_match_stats.', 'info')
        else:
            # Se la tabella non esiste, creala
            db.create_all()
            flash('✅ Tabella player_match_stats creata con successo!', 'success')
            
    except Exception as e:
        flash(f'❌ Errore durante la migrazione: {str(e)}', 'danger')
        print(f"Errore migrazione is_removed: {e}")
    
    return redirect(url_for('index'))

# ALTERNATIVO: Script manuale da eseguire nel terminale
def add_is_removed_column_manual():
    """Funzione da chiamare manualmente per aggiungere la colonna."""
    try:
        with app.app_context():
            inspector = db.inspect(db.engine)
            if inspector.has_table('player_match_stats'):
                columns = [col['name'] for col in inspector.get_columns('player_match_stats')]
                
                if 'is_removed' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(db.text('ALTER TABLE player_match_stats ADD COLUMN is_removed BOOLEAN DEFAULT 0'))
                        conn.commit()
                    print("✅ Colonna is_removed aggiunta con successo!")
                else:
                    print("ℹ️ La colonna is_removed esiste già.")
            else:
                print("❌ Tabella player_match_stats non trovata.")
                print("💡 Esegui prima db.create_all() per creare le tabelle.")
                
    except Exception as e:
        print(f"❌ Errore durante la migrazione: {e}")

# Per eseguire la migrazione manualmente nel terminale:
# python -c "from app import add_is_removed_column_manual; add_is_removed_column_manual()"



@app.route('/migrate_final_ranking', methods=['POST'])
def migrate_final_ranking():
    """Migra il database per aggiungere la tabella final_ranking."""
    try:
        # Crea tutte le tabelle (inclusa final_ranking se non esiste)
        db.create_all()
        flash('🏆 Tabella final_ranking creata con successo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante la migrazione final_ranking: {str(e)}', 'danger')
    
    return redirect(url_for('standings'))


@app.route('/migrate_best_player_fields', methods=['POST'])
def migrate_best_player_fields():
    """Migra il database aggiungendo i campi per il miglior giocatore."""
    try:
        # Controlla se le colonne esistono già
        inspector = db.inspect(db.engine)
        
        if db.inspect(db.engine).has_table('player_match_stats'):
            columns = [col['name'] for col in inspector.get_columns('player_match_stats')]
            
            if 'is_best_player_team1' not in columns:
                # Aggiungi le colonne per miglior giocatore
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE player_match_stats ADD COLUMN is_best_player_team1 BOOLEAN DEFAULT 0'))
                    conn.execute(db.text('ALTER TABLE player_match_stats ADD COLUMN is_best_player_team2 BOOLEAN DEFAULT 0'))
                    conn.commit()
                
                flash('Database migrato con successo! Campi miglior giocatore aggiunti.', 'success')
            else:
                flash('I campi miglior giocatore esistono già nel database.', 'info')
        else:
            # Se la tabella non esiste, creala
            db.create_all()
            flash('Tabella PlayerMatchStats creata con successo!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la migrazione del database: {str(e)}', 'danger')
    
    return redirect(url_for('index'))


@app.route('/debug_mvp')
def debug_mvp():
    """Debug: controlla i dati MVP nel database."""
    try:
        if db.inspect(db.engine).has_table('player_match_stats'):
            # Controlla se ci sono record con MVP
            mvp_records = PlayerMatchStats.query.filter(
                (PlayerMatchStats.is_best_player_team1 == True) | 
                (PlayerMatchStats.is_best_player_team2 == True)
            ).all()
            
            debug_info = []
            for record in mvp_records:
                player = Player.query.get(record.player_id)
                match = Match.query.get(record.match_id)
                debug_info.append({
                    'player_name': player.name if player else 'Sconosciuto',
                    'team_name': player.team.name if player and player.team else 'Sconosciuto',
                    'match_id': record.match_id,
                    'is_team1_mvp': record.is_best_player_team1,
                    'is_team2_mvp': record.is_best_player_team2,
                    'match_teams': f"{match.get_team1_display_name()} vs {match.get_team2_display_name()}" if match else 'Match non trovato'
                })
            
            flash(f'🔍 Debug MVP - Record trovati: {len(mvp_records)}. Dettagli: {debug_info}', 'info')
        else:
            flash('❌ Tabella player_match_stats non trovata! Esegui la migrazione.', 'danger')
    except Exception as e:
        flash(f'❌ Errore debug MVP: {str(e)}', 'danger')
    
    return redirect(url_for('standings'))


# Aggiungi questa route al tuo app.py per creare le tabelle

@app.route('/force_create_tables')
def force_create_tables():
    """Forza la creazione di tutte le tabelle."""
    try:
        # Importa tutti i modelli per assicurarsi che siano caricati
        from app import User, Team, Player, Match
        
        # Crea tutte le tabelle
        db.create_all()
        
        # Verifica che siano state create
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        # Crea utente admin di default
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', role='admin')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
        
        return f"""
        <h2>✅ Tabelle create con successo!</h2>
        <p><strong>Tabelle create:</strong> {', '.join(tables)}</p>
        <p><strong>User table exists:</strong> {'user' in tables}</p>
        <p><strong>Admin user created:</strong> admin / admin123</p>
        
        <h3>Test Login:</h3>
        <form method="post" action="/login">
            <input type="text" name="username" value="admin" placeholder="Username">
            <input type="password" name="password" value="admin123" placeholder="Password">
            <button type="submit">Test Login</button>
        </form>
        
        <p><a href="/">← Torna alla Home</a></p>
        """
        
    except Exception as e:
        return f"""
        <h2>❌ Errore nella creazione tabelle</h2>
        <p><strong>Errore:</strong> {str(e)}</p>
        <p><a href="/">← Torna alla Home</a></p>
        """


# Aggiungi questa route al tuo app.py per migrare i dati

@app.route('/migrate_from_sqlite', methods=['GET', 'POST'])
def migrate_from_sqlite():
    """Migra dati da SQLite locale a PostgreSQL."""
    
    if request.method == 'GET':
        return '''
        <h2>🔄 Migrazione da SQLite a PostgreSQL</h2>
        <p>Questa funzione migrerà tutti i dati dal database SQLite locale al PostgreSQL.</p>
        
        <form method="post" enctype="multipart/form-data">
            <h3>Upload del database SQLite:</h3>
            <input type="file" name="sqlite_file" accept=".db" required>
            <br><br>
            <label>
                <input type="checkbox" name="confirm" required>
                Confermo di voler migrare i dati (sovrascriverà i dati esistenti)
            </label>
            <br><br>
            <button type="submit">🚀 Inizia Migrazione</button>
        </form>
        
        <p><a href="/">← Torna alla Home</a></p>
        '''
    
    try:
        # Verifica checkbox di conferma
        if not request.form.get('confirm'):
            return "❌ Devi confermare la migrazione"
        
        # Ottieni il file caricato
        sqlite_file = request.files.get('sqlite_file')
        if not sqlite_file:
            return "❌ Nessun file caricato"
        
        # Salva temporaneamente il file
        import tempfile
        import sqlite3
        
        with tempfile.NamedTemporaryFile(suffix='.db') as temp_file:
            sqlite_file.save(temp_file.name)
            
            # Connessione al SQLite caricato
            sqlite_conn = sqlite3.connect(temp_file.name)
            sqlite_conn.row_factory = sqlite3.Row
            
            results = []
            
            # Lista delle tabelle da migrare nell'ordine corretto (eliminazione prima)
            tables_order = ['player_match_stats', 'match', 'player', 'team', 'user', 'tournament_config', 'all_star_team', 'final_ranking']
            
            for table_name in tables_order:
                try:
                    # Controlla se la tabella esiste nel SQLite
                    cursor = sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                    if not cursor.fetchone():
                        continue
                    
                    # Leggi tutti i dati dalla tabella SQLite
                    sqlite_cursor = sqlite_conn.execute(f"SELECT * FROM {table_name}")
                    rows = sqlite_cursor.fetchall()
                    
                    if not rows:
                        results.append(f"⚠️ {table_name}: 0 record")
                        continue
                    
                    # Elimina i dati esistenti in PostgreSQL per questa tabella (nell'ordine corretto)
                    if table_name == 'player_match_stats':
                        if db.inspect(db.engine).has_table('player_match_stats'):
                            PlayerMatchStats.query.delete()
                    elif table_name == 'match':
                        Match.query.delete()
                    elif table_name == 'player':
                        Player.query.delete()
                    elif table_name == 'team':
                        Team.query.delete()
                    elif table_name == 'user':
                        User.query.delete()
                    # Aggiungi altre tabelle se necessario
                    
                    db.session.commit()
                    
                    # Inserisci i nuovi dati
                    migrated_count = 0
                    for row in rows:
                        row_dict = dict(row)
                        
                        if table_name == 'user':
                            obj = User(**row_dict)
                        elif table_name == 'team':
                            obj = Team(**row_dict)
                        elif table_name == 'player':
                            obj = Player(**row_dict)
                        elif table_name == 'match':
                            obj = Match(**row_dict)
                        elif table_name == 'player_match_stats':
                            obj = PlayerMatchStats(**row_dict)
                        else:
                            continue
                        
                        db.session.add(obj)
                        migrated_count += 1
                    
                    db.session.commit()
                    results.append(f"✅ {table_name}: {migrated_count} record migrati")
                    
                except Exception as e:
                    db.session.rollback()
                    results.append(f"❌ {table_name}: Errore - {str(e)}")
            
            sqlite_conn.close()
        
        return f'''
        <h2>🎉 Migrazione Completata!</h2>
        <h3>Risultati:</h3>
        <ul>
        {''.join([f"<li>{result}</li>" for result in results])}
        </ul>
        
        <p><a href="/">← Vai alla Home per vedere i dati</a></p>
        '''
        
    except Exception as e:
        db.session.rollback()
        return f'''
        <h2>❌ Errore durante la migrazione</h2>
        <p><strong>Errore:</strong> {str(e)}</p>
        <p><a href="/migrate_from_sqlite">← Riprova</a></p>
        '''
# Aggiungi anche questa route per importare da CSV

@app.route('/import_from_csv', methods=['GET', 'POST'])
def import_from_csv():
    """Importa dati da file CSV (da export precedente)."""
    
    if request.method == 'GET':
        return '''
        <h2>📁 Importa da CSV</h2>
        <p>Carica il file ZIP esportato in precedenza con /export_database_csv</p>
        
        <form method="post" enctype="multipart/form-data">
            <h3>Upload del file ZIP:</h3>
            <input type="file" name="csv_zip" accept=".zip" required>
            <br><br>
            <label>
                <input type="checkbox" name="confirm" required>
                Confermo di voler importare i dati
            </label>
            <br><br>
            <button type="submit">📤 Importa Dati</button>
        </form>
        
        <p><a href="/">← Torna alla Home</a></p>
        '''
    
    try:
        import zipfile
        import csv
        import tempfile
        from io import StringIO
        
        # Verifica conferma
        if not request.form.get('confirm'):
            return "❌ Devi confermare l'importazione"
        
        # Ottieni il file ZIP
        zip_file = request.files.get('csv_zip')
        if not zip_file:
            return "❌ Nessun file caricato"
        
        results = []
        
        with tempfile.NamedTemporaryFile() as temp_file:
            zip_file.save(temp_file.name)
            
            with zipfile.ZipFile(temp_file.name, 'r') as zf:
                
                # Importa squadre
                if 'teams.csv' in zf.namelist():
                    Team.query.delete()
                    teams_csv = zf.read('teams.csv').decode('utf-8')
                    reader = csv.DictReader(StringIO(teams_csv))
                    count = 0
                    for row in reader:
                        team = Team(
                            name=row['name'],
                            group=row['group'],
                            wins=int(row['wins'] or 0),
                            losses=int(row['losses'] or 0),
                            draws=int(row['draws'] or 0),
                            goals_for=int(row['goals_for'] or 0),
                            goals_against=int(row['goals_against'] or 0),
                            points=int(row['points'] or 0)
                        )
                        db.session.add(team)
                        count += 1
                    db.session.commit()
                    results.append(f"✅ Squadre: {count} importate")
                
                # Importa giocatori
                if 'players.csv' in zf.namelist():
                    Player.query.delete()
                    players_csv = zf.read('players.csv').decode('utf-8')
                    reader = csv.DictReader(StringIO(players_csv))
                    count = 0
                    for row in reader:
                        team = Team.query.filter_by(name=row['team_name']).first()
                        if team:
                            player = Player(
                                name=row['name'],
                                team_id=team.id,
                                is_registered=row['is_registered'].lower() == 'true',
                                category=row['category'] if row['category'] != 'None' else None,
                                goals=int(row['goals'] or 0),
                                assists=int(row['assists'] or 0),
                                penalties=int(row['penalties'] or 0)
                            )
                            db.session.add(player)
                            count += 1
                    db.session.commit()
                    results.append(f"✅ Giocatori: {count} importati")
                
                # Importa partite
                if 'matches.csv' in zf.namelist():
                    Match.query.delete()
                    matches_csv = zf.read('matches.csv').decode('utf-8')
                    reader = csv.DictReader(StringIO(matches_csv))
                    count = 0
                    for row in reader:
                        team1 = Team.query.filter_by(name=row['team1_name']).first()
                        team2 = Team.query.filter_by(name=row['team2_name']).first()
                        
                        if team1 and team2:
                            match = Match(
                                team1_id=team1.id,
                                team2_id=team2.id,
                                date=datetime.strptime(row['date'], '%Y-%m-%d').date() if row['date'] else None,
                                time=datetime.strptime(row['time'], '%H:%M').time() if row['time'] else None,
                                team1_score=int(row['team1_score']) if row['team1_score'] else None,
                                team2_score=int(row['team2_score']) if row['team2_score'] else None,
                                is_completed=row['is_completed'].lower() == 'true',
                                phase=row['phase'],
                                league=row['league'] if row['league'] else None
                            )
                            db.session.add(match)
                            count += 1
                    db.session.commit()
                    results.append(f"✅ Partite: {count} importate")
        
        return f'''
        <h2>🎉 Importazione Completata!</h2>
        <h3>Risultati:</h3>
        <ul>
        {''.join([f"<li>{result}</li>" for result in results])}
        </ul>
        
        <p><a href="/">← Vai alla Home per vedere i dati</a></p>
        '''
        
    except Exception as e:
        db.session.rollback()
        return f'''
        <h2>❌ Errore durante l'importazione</h2>
        <p><strong>Errore:</strong> {str(e)}</p>
        <p><a href="/import_from_csv">← Riprova</a></p>
        '''

@app.route('/debug_mvp_awards')
def debug_mvp_awards():
    """Debug: controlla la funzione get_best_player_awards."""
    try:
        awards = get_best_player_awards()
        
        debug_info = {
            'awards_count': len(awards),
            'awards_details': []
        }
        
        for player, count in awards:
            debug_info['awards_details'].append({
                'player_name': player.name,
                'team_name': player.team.name,
                'awards_count': count
            })
        
        flash(f'🏆 Debug Awards Function: {debug_info}', 'info')
        
    except Exception as e:
        flash(f'❌ Errore nella funzione get_best_player_awards: {str(e)}', 'danger')
        import traceback
        flash(f'Traceback: {traceback.format_exc()}', 'danger')
    
    return redirect(url_for('standings'))


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



# def update_team_stats(match, old_team1_score=None, old_team2_score=None):
#     """Aggiorna le statistiche delle squadre e controlla aggiornamenti playoff automatici."""
#     team1 = match.team1
#     team2 = match.team2

#     # Se esistono vecchi punteggi, sottraiamo quei valori dalle statistiche delle squadre
#     if old_team1_score is not None and old_team2_score is not None:
#         team1.goals_for -= old_team1_score
#         team1.goals_against -= old_team2_score
#         team2.goals_for -= old_team2_score
#         team2.goals_against -= old_team1_score

#         if old_team1_score > old_team2_score:
#             team1.wins -= 1
#             team2.losses -= 1
#             team1.points -= 3
#         elif old_team2_score > old_team1_score:
#             team2.wins -= 1
#             team1.losses -= 1
#             team2.points -= 3
#         else:
#             team1.draws -= 1
#             team2.draws -= 1
#             team1.points -= 1
#             team2.points -= 1

#     # Aggiungiamo i nuovi valori alle statistiche
#     team1.goals_for += match.team1_score
#     team1.goals_against += match.team2_score
#     team2.goals_for += match.team2_score
#     team2.goals_against += match.team1_score

#     if match.team1_score > match.team2_score:
#         team1.wins += 1
#         team2.losses += 1
#         team1.points += 3
#     elif match.team2_score > match.team1_score:
#         team2.wins += 1
#         team1.losses += 1
#         team2.points += 3
#     else:
#         team1.draws += 1
#         team2.draws += 1
#         team1.points += 1
#         team2.points += 1

#     # *** AGGIORNAMENTI AUTOMATICI PLAYOFF ***
    
#     # 1. QUALIFICAZIONI COMPLETATE → AGGIORNA QUARTI
#     if match.phase == 'group' and all_group_matches_completed():
#         print("🎯 Tutte le qualificazioni completate! Aggiornamento quarti automatico...")
#         try:
#             update_playoff_brackets()
#             print("✅ Quarti aggiornati automaticamente!")
#         except Exception as e:
#             print(f"❌ Errore aggiornamento quarti: {e}")
    
#     # 2. QUARTI COMPLETATI PER UNA LEGA → AGGIORNA SEMIFINALI DI QUELLA LEGA
#     if match.phase == 'quarterfinal':
#         league = match.league
#         if league and all_phase_matches_completed('quarterfinal', league):
#             print(f"🎯 Quarti {league} completati! Aggiornamento semifinali automatico...")
#             try:
#                 update_semifinals(league)
#                 print(f"✅ Semifinali {league} aggiornate automaticamente!")
#             except Exception as e:
#                 print(f"❌ Errore aggiornamento semifinali {league}: {e}")
    
#     # 3. SEMIFINALI COMPLETATE PER UNA LEGA → AGGIORNA FINALI DI QUELLA LEGA
#     if match.phase == 'semifinal':
#         league = match.league
#         if league and all_phase_matches_completed('semifinal', league):
#             print(f"🎯 Semifinali {league} completate! Aggiornamento finali automatico...")
#             try:
#                 update_finals(league)
#                 print(f"✅ Finali {league} aggiornate automaticamente!")
#             except Exception as e:
#                 print(f"❌ Errore aggiornamento finali {league}: {e}")


def update_team_stats(match, old_team1_score=None, old_team2_score=None, old_overtime=None, old_shootout=None):
    """Aggiorna le statistiche delle squadre usando il sistema punti hockey E controlla aggiornamenti playoff automatici."""
    
    team1 = match.team1
    team2 = match.team2

    # Se esistono vecchi punteggi, sottrai quei valori dalle statistiche
    if old_team1_score is not None and old_team2_score is not None:
        team1.goals_for -= old_team1_score
        team1.goals_against -= old_team2_score
        team2.goals_for -= old_team2_score
        team2.goals_against -= old_team1_score

        # Crea match temporaneo con i vecchi valori per calcolare i punti da sottrarre
        old_match = type('OldMatch', (), {
            'team1_score': old_team1_score,
            'team2_score': old_team2_score,
            'overtime': old_overtime or False,
            'shootout': old_shootout or False,
            'is_completed': True,
            'winner': team1 if old_team1_score > old_team2_score else (team2 if old_team2_score > old_team1_score else None),
            'is_regulation_time': not (old_overtime or old_shootout),
            'is_overtime_shootout': old_overtime or old_shootout
        })()
        old_match.get_points_for_team = match.get_points_for_team.__func__
        
        # Sottrai i vecchi punti
        old_team1_points = old_match.get_points_for_team(old_match, team1)
        old_team2_points = old_match.get_points_for_team(old_match, team2)
        team1.points -= old_team1_points
        team2.points -= old_team2_points

        # Aggiorna record vittorie/sconfitte/pareggi (sottrai vecchi)
        if old_team1_score > old_team2_score:
            team1.wins -= 1
            team2.losses -= 1
        elif old_team2_score > old_team1_score:
            team2.wins -= 1
            team1.losses -= 1
        else:
            team1.draws -= 1
            team2.draws -= 1

    # Aggiungi i nuovi valori alle statistiche
    team1.goals_for += match.team1_score
    team1.goals_against += match.team2_score
    team2.goals_for += match.team2_score
    team2.goals_against += match.team1_score

    # Calcola i nuovi punti usando il sistema hockey
    team1_points = match.get_points_for_team(team1)
    team2_points = match.get_points_for_team(team2)
    team1.points += team1_points
    team2.points += team2_points

    # Aggiorna record vittorie/sconfitte/pareggi (aggiungi nuovi)
    if match.team1_score > match.team2_score:
        team1.wins += 1
        team2.losses += 1
    elif match.team2_score > match.team1_score:
        team2.wins += 1
        team1.losses += 1
    else:
        team1.draws += 1
        team2.draws += 1

    # Debug info
    print(f"🏒 {team1.name} {match.team1_score}-{match.team2_score} {team2.name}")
    print(f"   Overtime: {match.overtime}, Rigori: {match.shootout}")
    print(f"   Punti: {team1.name}={team1_points}, {team2.name}={team2_points}")

    # *** AGGIORNAMENTI AUTOMATICI PLAYOFF ***
    print(f"🔍 Controllo aggiornamenti automatici per partita fase: {match.phase}")
    
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


@app.route('/check_incomplete_matches', methods=['POST'])
def all_group_matches_completed():
    incomplete_matches = Match.query.filter_by(phase='group').filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    print(f"🔍 Controllo partite gironi incomplete: {incomplete_matches} trovate ")
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
    
    # USAR LE NUOVE FUNZIONI per ottenere le classifiche corrette
    group_standings = get_group_standings()
    
    # Debug: mostra le classifiche
    for group, teams in group_standings.items():
        print(f"📊 Girone {group}: {[f'{t.name}({t.group_points}pts)' for t in teams]}")
    
    # Verifica che ogni girone abbia almeno 4 squadre
    for group in ['A', 'B', 'C', 'D']:
        if len(group_standings[group]) < 4:
            print(f"❌ Girone {group} ha solo {len(group_standings[group])} squadre!")
            return False
    
    try:
        # Aggiorna i quarti di finale Major League
        ml_quarters = Match.query.filter_by(phase='quarterfinal', league='Major League').order_by(Match.time).all()
        
        # Accoppiamenti Major League: 1D vs 2C, 1A vs 2B, 1C vs 2A, 1B vs 2D
        ml_matchups = [
            (group_standings['D'][0], group_standings['C'][1]),  # 1D vs 2C
            (group_standings['A'][0], group_standings['B'][1]),  # 1A vs 2B
            (group_standings['C'][0], group_standings['A'][1]),  # 1C vs 2A
            (group_standings['B'][0], group_standings['D'][1]),  # 1B vs 2D
        ]
        
        print("🔄 Aggiornamento Major League:")
        for i, (team1, team2) in enumerate(ml_matchups):
            if i < len(ml_quarters):
                ml_quarters[i].team1_id = team1.id
                ml_quarters[i].team2_id = team2.id
                print(f"  Partita {i+1}: {team1.name} vs {team2.name}")
        
        # Aggiorna i quarti di finale Beer League
        bl_quarters = Match.query.filter_by(phase='quarterfinal', league='Beer League').order_by(Match.time).all()
        
        # Accoppiamenti Beer League: 3B vs 4A, 3D vs 4C, 3A vs 4D, 3C vs 4B
        bl_matchups = [
            (group_standings['B'][2], group_standings['A'][3]),  # 3B vs 4A
            (group_standings['D'][2], group_standings['C'][3]),  # 3D vs 4C
            (group_standings['A'][2], group_standings['D'][3]),  # 3A vs 4D
            (group_standings['C'][2], group_standings['B'][3]),  # 3C vs 4B
        ]
        
        print("🔄 Aggiornamento Beer League:")
        for i, (team1, team2) in enumerate(bl_matchups):
            if i < len(bl_quarters):
                bl_quarters[i].team1_id = team1.id
                bl_quarters[i].team2_id = team2.id
                print(f"  Partita {i+1}: {team1.name} vs {team2.name}")
        
        db.session.commit()
        print("✅ Playoff brackets aggiornati con successo!")
        return True
        
    except Exception as e:
        print(f"❌ Errore durante l'aggiornamento playoff: {e}")
        db.session.rollback()
        return False



def all_quarterfinals_completed(league):
    incomplete_matches = Match.query.filter_by(
        phase='quarterfinal', league=league
    ).filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    return incomplete_matches == 0


def update_semifinals(league):
    """Aggiorna le semifinali di una lega specifica con i vincitori/perdenti dei quarti."""
    print(f"🔄 Aggiornamento semifinali {league}...")
    
    # Ottieni i quarti di finale della lega completati
    quarterfinals = Match.query.filter_by(
        phase='quarterfinal', 
        league=league
    ).order_by(Match.time).all()
    
    if len(quarterfinals) != 4:
        print(f"❌ Errore: {league} dovrebbe avere 4 quarti, trovati {len(quarterfinals)}")
        return False
    
    # Verifica che tutti i quarti siano completati
    for quarter in quarterfinals:
        if not quarter.is_completed:
            print(f"❌ Quarto {quarter.id} non completato")
            return False
    
    # Ottieni vincitori e perdenti
    winners = []
    losers = []
    for quarter in quarterfinals:
        winner = quarter.winner
        loser = quarter.team1 if winner == quarter.team2 else quarter.team2
        winners.append(winner)
        losers.append(loser)
    
    print(f"🏆 Vincenti: {[w.name for w in winners]}")
    print(f"💔 Perdenti: {[l.name for l in losers]}")
    
    # Ottieni le semifinali della lega
    semifinals = Match.query.filter_by(
        phase='semifinal',
        league=league
    ).order_by(Match.time).all()
    
    if len(semifinals) != 4:
        print(f"❌ Errore: {league} dovrebbe avere 4 semifinali, trovate {len(semifinals)}")
        return False
    
    # Aggiorna le semifinali
    # Semifinali perdenti (prime due partite)
    semifinals[0].team1_id = losers[2].id  # Perdente Q1
    semifinals[0].team2_id = losers[3].id  # Perdente Q2
    semifinals[1].team1_id = losers[0].id  # Perdente Q3  
    semifinals[1].team2_id = losers[1].id  # Perdente Q4
    
    # Semifinali vincenti (ultime due partite)
    semifinals[2].team1_id = winners[2].id  # Vincente Q1
    semifinals[2].team2_id = winners[3].id  # Vincente Q2
    semifinals[3].team1_id = winners[0].id  # Vincente Q3
    semifinals[3].team2_id = winners[1].id  # Vincente Q4
    
    db.session.commit()
    print(f"✅ Semifinali {league} aggiornate")
    return True


def update_finals(league):
    """Aggiorna le finali di una lega specifica con i vincitori/perdenti delle semifinali."""
    print(f"🔄 Aggiornamento finali {league}...")
    
    # Ottieni le semifinali della lega completate
    semifinals = Match.query.filter_by(
        phase='semifinal',
        league=league
    ).order_by(Match.time).all()
    
    if len(semifinals) != 4:
        print(f"❌ Errore: {league} dovrebbe avere 4 semifinali, trovate {len(semifinals)}")
        return False
    
    # Verifica che tutte le semifinali siano completate
    for semi in semifinals:
        if not semi.is_completed:
            print(f"❌ Semifinale {semi.id} non completata")
            return False
    
    # Ottieni vincitori e perdenti delle semifinali
    # Prime due semifinali = perdenti quarti, ultime due = vincenti quarti
    losers_bracket_winners = [semifinals[0].winner, semifinals[1].winner]
    winners_bracket_winners = [semifinals[2].winner, semifinals[3].winner]
    losers_bracket_losers = [
        semifinals[0].team1 if semifinals[0].winner == semifinals[0].team2 else semifinals[0].team2,
        semifinals[1].team1 if semifinals[1].winner == semifinals[1].team2 else semifinals[1].team2
    ]
    winners_bracket_losers = [
        semifinals[2].team1 if semifinals[2].winner == semifinals[2].team2 else semifinals[2].team2,
        semifinals[3].team1 if semifinals[3].winner == semifinals[3].team2 else semifinals[3].team2
    ]
    
    print(f"🏆 Vincenti bracket perdenti: {[w.name for w in losers_bracket_winners]}")
    print(f"🏆 Vincenti bracket vincenti: {[w.name for w in winners_bracket_winners]}")
    
    # Ottieni le finali della lega
    finals = Match.query.filter_by(
        phase='final',
        league=league
    ).order_by(Match.time).all()
    
    if len(finals) != 4:
        print(f"❌ Errore: {league} dovrebbe avere 4 finali, trovate {len(finals)}")
        return False
    
    # Aggiorna le finali
    # Finale 7°/8° posto
    finals[0].team1_id = losers_bracket_losers[0].id
    finals[0].team2_id = losers_bracket_losers[1].id
    
    # Finale 5°/6° posto  
    finals[1].team1_id = losers_bracket_winners[0].id
    finals[1].team2_id = losers_bracket_winners[1].id
    
    # Finale 3°/4° posto
    finals[2].team1_id = winners_bracket_losers[0].id
    finals[2].team2_id = winners_bracket_losers[1].id
    
    # Finale 1°/2° posto
    finals[3].team1_id = winners_bracket_winners[0].id
    finals[3].team2_id = winners_bracket_winners[1].id
    
    db.session.commit()
    print(f"✅ Finali {league} aggiornate")
    return True


def all_semifinals_completed(league):
    incomplete_matches = Match.query.filter_by(
        phase='semifinal', league=league
    ).filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    return incomplete_matches == 0





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
@login_required
@admin_required 
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



# @app.route('/reset_db', methods=['POST'])
# def reset_db():
#     if request.form.get('confirm') == 'yes':
#         # Drop all tables
#         db.drop_all()
#         # Recreate all tables
#         db.create_all()
#         flash('Il database è stato azzerato con successo', 'success')
#     else:
#         flash('Conferma non ricevuta. Il database non è stato azzerato.', 'warning')
#     return redirect(url_for('index'))

# Aggiungi queste route nel file app.py

@app.route('/reset_schedule', methods=['POST'])
def reset_schedule():
    """Azzera calendario partite e statistiche."""
    reset_matches()
    return redirect(url_for('settings'))

def reset_matches():
    """Elimina tutte le partite e azzera tutte le statistiche."""
    try:
        # Elimina le descrizioni delle partite
        MatchDescription.query.delete()
        
        # Elimina le statistiche per partita dei giocatori (se esiste la tabella)
        try:
            if db.inspect(db.engine).has_table('player_match_stats'):
                PlayerMatchStats.query.delete()
        except:
            pass
        
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
        
        # Azzerare le statistiche dei giocatori
        players = Player.query.all()
        for player in players:
            player.goals = 0
            player.assists = 0
            player.penalties = 0
        
        # Elimina classifiche finali e All Star Team
        try:
            if db.inspect(db.engine).has_table('final_ranking'):
                FinalRanking.query.delete()
        except:
            pass
        
        try:
            if db.inspect(db.engine).has_table('all_star_team'):
                AllStarTeam.query.delete()
        except:
            pass
        
        db.session.commit()
        flash('✅ Calendario e statistiche azzerati con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore nell\'azzeramento: {str(e)}', 'danger')

@app.route('/export_database_csv')
def export_database_csv():
    """Esporta tutto il database in file CSV compressi."""
    try:
        import zipfile
        import csv
        from io import StringIO
        import tempfile
        import os
        from datetime import datetime
        
        # Crea un file temporaneo per il ZIP
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'database_export.zip')
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            
            # TABELLA TEAMS
            teams = Team.query.all()
            if teams:
                csv_buffer = StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(['id', 'name', 'group', 'wins', 'losses', 'draws', 'goals_for', 'goals_against', 'points'])
                for team in teams:
                    writer.writerow([team.id, team.name, team.group, team.wins, team.losses, 
                                   team.draws, team.goals_for, team.goals_against, team.points])
                zipf.writestr('teams.csv', csv_buffer.getvalue())
            
            # TABELLA PLAYERS
            players = Player.query.all()
            if players:
                csv_buffer = StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(['id', 'name', 'team_id', 'team_name', 'is_registered', 'category', 'goals', 'assists', 'penalties'])
                for player in players:
                    writer.writerow([player.id, player.name, player.team_id, player.team.name, 
                                   player.is_registered, player.category, player.goals, player.assists, player.penalties])
                zipf.writestr('players.csv', csv_buffer.getvalue())
            
            # TABELLA MATCHES
            matches = Match.query.all()
            if matches:
                csv_buffer = StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(['id', 'team1_name', 'team2_name', 'date', 'time', 'team1_score', 'team2_score', 
                               'is_completed', 'phase', 'league', 'winner_name'])
                for match in matches:
                    writer.writerow([
                        match.id, 
                        match.team1.name if match.team1 else 'TBD',
                        match.team2.name if match.team2 else 'TBD',
                        match.date.strftime('%Y-%m-%d') if match.date else '',
                        match.time.strftime('%H:%M') if match.time else '',
                        match.team1_score, match.team2_score, match.is_completed,
                        match.phase, match.league,
                        match.winner.name if match.winner else ''
                    ])
                zipf.writestr('matches.csv', csv_buffer.getvalue())
            
            # TABELLA PLAYER_MATCH_STATS (se esiste)
            try:
                if db.inspect(db.engine).has_table('player_match_stats'):
                    stats = PlayerMatchStats.query.all()
                    if stats:
                        csv_buffer = StringIO()
                        writer = csv.writer(csv_buffer)
                        writer.writerow(['id', 'player_name', 'match_id', 'goals', 'assists', 'penalties'])
                        for stat in stats:
                            writer.writerow([stat.id, stat.player.name, stat.match_id, 
                                           stat.goals, stat.assists, stat.penalties])
                        zipf.writestr('player_match_stats.csv', csv_buffer.getvalue())
            except:
                pass
            
            # TABELLA FINAL_RANKING (se esiste)
            try:
                if db.inspect(db.engine).has_table('final_ranking'):
                    rankings = FinalRanking.query.all()
                    if rankings:
                        csv_buffer = StringIO()
                        writer = csv.writer(csv_buffer)
                        writer.writerow(['id', 'team_name', 'final_position'])
                        for ranking in rankings:
                            writer.writerow([ranking.id, ranking.team.name, ranking.final_position])
                        zipf.writestr('final_rankings.csv', csv_buffer.getvalue())
            except:
                pass
            
            # TABELLA ALL_STAR_TEAM (se esiste)
            try:
                if db.inspect(db.engine).has_table('all_star_team'):
                    selections = AllStarTeam.query.all()
                    if selections:
                        csv_buffer = StringIO()
                        writer = csv.writer(csv_buffer)
                        writer.writerow(['id', 'player_name', 'team_name', 'position', 'category'])
                        for selection in selections:
                            writer.writerow([selection.id, selection.player.name, selection.player.team.name,
                                           selection.position, selection.category])
                        zipf.writestr('all_star_team.csv', csv_buffer.getvalue())
            except:
                pass
            
            # TABELLA TOURNAMENT_SETTINGS (se esiste)
            try:
                if db.inspect(db.engine).has_table('tournament_settings'):
                    settings = TournamentSettings.query.all()
                    if settings:
                        csv_buffer = StringIO()
                        writer = csv.writer(csv_buffer)
                        writer.writerow(['id', 'tournament_name', 'qualification_day1', 'qualification_day2', 
                                       'finals_date', 'max_teams', 'teams_per_group', 'max_registration_points'])
                        for setting in settings:
                            writer.writerow([setting.id, setting.tournament_name, setting.qualification_day1,
                                           setting.qualification_day2, setting.finals_date, setting.max_teams,
                                           setting.teams_per_group, setting.max_registration_points])
                        zipf.writestr('tournament_settings.csv', csv_buffer.getvalue())
            except:
                pass
            
            # CLASSIFICHE CALCOLATE - Aggiunte nuove (DENTRO il with zipfile)
            
            # CLASSIFICA MARCATORI
            try:
                if db.inspect(db.engine).has_table('player_match_stats'):
                    from sqlalchemy import func
                    
                    top_scorers_query = db.session.query(
                        Player,
                        func.sum(PlayerMatchStats.goals).label('total_goals'),
                        func.count(PlayerMatchStats.match_id).label('total_matches'),
                        func.sum(PlayerMatchStats.assists).label('total_assists')
                    ).join(PlayerMatchStats).group_by(Player.id).having(
                        func.sum(PlayerMatchStats.goals) > 0
                    ).order_by(
                        func.sum(PlayerMatchStats.goals).desc(),
                        func.count(PlayerMatchStats.match_id).asc(),
                        func.sum(PlayerMatchStats.assists).desc()
                    ).all()
                    
                    if top_scorers_query:
                        csv_buffer = StringIO()
                        writer = csv.writer(csv_buffer)
                        writer.writerow(['posizione', 'giocatore', 'squadra', 'gol', 'partite_giocate', 'assist'])
                        for i, (player, total_goals, total_matches, total_assists) in enumerate(top_scorers_query, 1):
                            writer.writerow([i, player.name, player.team.name, total_goals, total_matches, total_assists or 0])
                        zipf.writestr('classifica_marcatori.csv', csv_buffer.getvalue())
            except Exception as e:
                print(f"Errore export marcatori: {e}")
            
            # CLASSIFICA ASSIST
            try:
                if db.inspect(db.engine).has_table('player_match_stats'):
                    top_assists_query = db.session.query(
                        Player,
                        func.sum(PlayerMatchStats.assists).label('total_assists'),
                        func.count(PlayerMatchStats.match_id).label('total_matches'),
                        func.sum(PlayerMatchStats.goals).label('total_goals')
                    ).join(PlayerMatchStats).group_by(Player.id).having(
                        func.sum(PlayerMatchStats.assists) > 0
                    ).order_by(
                        func.sum(PlayerMatchStats.assists).desc(),
                        func.count(PlayerMatchStats.match_id).asc(),
                        func.sum(PlayerMatchStats.goals).desc()
                    ).all()
                    
                    if top_assists_query:
                        csv_buffer = StringIO()
                        writer = csv.writer(csv_buffer)
                        writer.writerow(['posizione', 'giocatore', 'squadra', 'assist', 'partite_giocate', 'gol'])
                        for i, (player, total_assists, total_matches, total_goals) in enumerate(top_assists_query, 1):
                            writer.writerow([i, player.name, player.team.name, total_assists, total_matches, total_goals or 0])
                        zipf.writestr('classifica_assist.csv', csv_buffer.getvalue())
            except Exception as e:
                print(f"Errore export assist: {e}")
            
            # CLASSIFICA PENALITÀ
            try:
                if db.inspect(db.engine).has_table('player_match_stats'):
                    top_penalties_query = db.session.query(
                        Player,
                        func.sum(PlayerMatchStats.penalties).label('total_penalties')
                    ).join(PlayerMatchStats).group_by(Player.id).having(
                        func.sum(PlayerMatchStats.penalties) > 0
                    ).order_by(func.sum(PlayerMatchStats.penalties).desc()).all()
                    
                    if top_penalties_query:
                        csv_buffer = StringIO()
                        writer = csv.writer(csv_buffer)
                        writer.writerow(['posizione', 'giocatore', 'squadra', 'penalita_minuti'])
                        for i, (player, total_penalties) in enumerate(top_penalties_query, 1):
                            writer.writerow([i, player.name, player.team.name, total_penalties])
                        zipf.writestr('classifica_penalita.csv', csv_buffer.getvalue())
            except Exception as e:
                print(f"Errore export penalità: {e}")
            
            # MVP AWARDS
            try:
                mvp_awards = get_best_player_awards()
                if mvp_awards:
                    csv_buffer = StringIO()
                    writer = csv.writer(csv_buffer)
                    writer.writerow(['posizione', 'giocatore', 'squadra', 'mvp_awards'])
                    for i, (player, awards_count) in enumerate(mvp_awards, 1):
                        writer.writerow([i, player.name, player.team.name, awards_count])
                    zipf.writestr('mvp_awards.csv', csv_buffer.getvalue())
            except Exception as e:
                print(f"Errore export MVP: {e}")
            
            # FAIR PLAY RANKING
            try:
                fair_play_data = get_fair_play_ranking()
                if fair_play_data:
                    csv_buffer = StringIO()
                    writer = csv.writer(csv_buffer)
                    writer.writerow(['posizione', 'squadra', 'girone', 'minuti_penalita', 'posizione_finale', 'has_final_ranking'])
                    for i, entry in enumerate(fair_play_data, 1):
                        if isinstance(entry, dict):
                            team_name = entry['team'].name
                            team_group = entry['team'].group or 'N/A'
                            penalty_minutes = entry['penalty_minutes']
                            final_position = entry['final_position']
                            has_final_ranking = entry.get('has_final_ranking', True)
                        else:
                            team_name = entry.team.name
                            team_group = entry.team.group or 'N/A'
                            penalty_minutes = entry.penalty_minutes
                            final_position = entry.final_position
                            has_final_ranking = getattr(entry, 'has_final_ranking', True)
                        
                        writer.writerow([i, team_name, team_group, penalty_minutes, final_position, has_final_ranking])
                    zipf.writestr('fair_play_ranking.csv', csv_buffer.getvalue())
            except Exception as e:
                print(f"Errore export Fair Play: {e}")
            
            # CLASSIFICHE GIRONI
            try:
                csv_buffer = StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(['girone', 'posizione', 'squadra', 'partite_giocate', 'vittorie', 'pareggi', 
                               'sconfitte', 'gol_fatti', 'gol_subiti', 'differenza_reti', 'punti'])
                
                for group in ['A', 'B', 'C', 'D']:
                    teams = Team.query.filter_by(group=group).order_by(
                        Team.points.desc(), 
                        (Team.goals_for - Team.goals_against).desc(),
                        Team.goals_for.desc()
                    ).all()
                    
                    for pos, team in enumerate(teams, 1):
                        writer.writerow([
                            group, pos, team.name, team.games_played, team.wins, team.draws,
                            team.losses, team.goals_for, team.goals_against, team.goal_difference, team.points
                        ])
                
                zipf.writestr('classifiche_gironi.csv', csv_buffer.getvalue())
            except Exception as e:
                print(f"Errore export gironi: {e}")
        
        # Genera nome file con data
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Database_Export_{date_str}.zip"
        
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        flash(f'❌ Errore nell\'export del database: {str(e)}', 'danger')
        return redirect(url_for('settings'))

@app.route('/reset_database', methods=['POST'])
def reset_database():
    """ATTENZIONE: Cancella TUTTO il database e ricrea le tabelle vuote."""
    try:
        # Conferma doppia sicurezza
        confirmation = request.form.get('confirmation')
        if confirmation != 'CANCELLA_TUTTO':
            flash('❌ Conferma non valida. Scrivi esattamente "CANCELLA_TUTTO" per confermare.', 'danger')
            return redirect(url_for('settings'))
        
        # Drop tutte le tabelle
        db.drop_all()
        
        # Ricrea le tabelle vuote
        db.create_all()
        
        # Ricrea settings di default
        TournamentSettings.create_default()
        
        flash('🗑️ Database completamente azzerato e ricreato!', 'warning')
        
    except Exception as e:
        flash(f'❌ Errore nel reset del database: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))
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
        (standings['D'][0], standings['C'][1]),  # 1D vs 2C
        (standings['A'][0], standings['B'][1]),  # 1A vs 2B
        (standings['C'][0], standings['A'][1]),  # 1C vs 2A
        (standings['B'][0], standings['D'][1]),  # 1B vs 2D
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
        (standings['B'][2], standings['A'][3]),  # 3B vs 4A
        (standings['D'][2], standings['C'][3]),  # 3D vs 4C
        (standings['A'][2], standings['D'][3]),  # 3A vs 4D
        (standings['C'][2], standings['B'][3]),  # 3C vs 4B
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
        'Major League': [time(11, 0), time(13, 0), time(15, 0), time(17, 0)],
        'Beer League': [time(10, 0), time(12, 0), time(14, 0), time(16, 0)]
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
        'AROSIO CAPITALS', 'DRUNK DUDES', 'FLORY MOTOS', 'GIÜGADUU DALA LIPPA',
        'YELLOWSTONE', 'BARDOLINO TEAM DOC', 'TIRABÜSCION', 'HOCKTAIL',
        'HC CATERPILLARS', 'I GAMB ROTT', 'PEPPA BEER', 'ORIGINAL TWINS'
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
            'A': ['BARRHOCK', 'YELLOWSTONE', 'FLORY MOTOS', 'HOCKTAIL'],
            'B': ['ORIGINAL TWINS', 'AROSIO CAPITALS', 'ANIMALS TEAM', 'I GAMB ROTT'],
            'C': ['PEPPA BEER', 'TIRABÜSCION', 'BARDOLINO TEAM DOC', 'LE PADELLE'],
            'D': ['DRUNK JUNIORS', 'DRUNK DUDES', 'HC CATERPILLARS', 'GIÜGADUU DALA LIPPA']
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
        # print("Step 2: Creazione giocatori...")
        # populate_players()
        
        # Step 3: Genera il calendario delle qualificazioni
        # print("Step 3: Generazione calendario...")
        # generate_complete_tournament_simple()
        
        # # Step 4: Reset e popola risultati delle qualificazioni con statistiche realistiche
        # print("Step 4: Popolamento risultati qualificazioni...")
        # reset_all_player_match_stats()  # Reset statistiche esistenti
        # populate_qualification_results()
        
        # Step 5: Aggiorna i playoff con le squadre qualificate
        # print("Step 5: Aggiornamento playoff...")
        # update_playoff_brackets()
        
        # flash('Database popolato con successo con dati di esempio!', 'success')
        
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
            # populate_players()
            flash('Step 2 completato: Giocatori creati', 'success')
            
        elif step == '3':
            # Solo calendario
            generate_qualification_matches_simple()
            generate_all_playoff_matches_simple()
            flash('Step 3 completato: Calendario generato', 'success')
            
        elif step == '4':
            # Solo risultati qualificazioni
            reset_all_player_match_stats()
            # populate_qualification_results()
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

@app.route('/insert_all_players', methods=['POST'])
def insert_all_players():
    """Inserisce tutti i giocatori con calcolo punti corretto."""
    
    players_data = {
        'DRUNK JUNIORS': [
            ('Gianluca Antoni', True, 'LNA/LNB'),
            ('Lorenzo Manfrini', True, 'LNA/LNB'),
            ('Eros Radaelli', True, '2a Lega'),
            ('Milo Meierhofer', True, '2a Lega'),
            ('Tommaso Mercolli', True, '2a Lega'),
            ('David Barchi', True, '2a Lega'),
            ('Giorgio Stefani', False, None),
            ('Matteo Destefani', False, None),
            ('Nicolò Mogliazzi', True, '2a Lega'),
            ('Andrea Pedrolini', True, 'Veterani'),
            ('Samuele Brusa', True, 'LNA/LNB'),
            ('Alex Weber', False, None),
            ('Jonas Fontana', False, None),
            ('Yvan Zanoli', False, None),
        ],
        'HC CATERPILLARS': [
            ('Gabriele Cicchinelli', True, '2a Lega'),
            ('Marzio Luvini', True, 'LNA/LNB'),
            ('Marco Ruspini', True, '2a Lega'),
            ('Manuel Ceresa', True, 'LNA/LNB'),
            ('Nuno Goncalves', False, None),
            ('Nelson Romelli', False, None),
            ('Marco Bortolotti', False, None),
            ('Luca Lischetti', False, None),
            ('Flavio Vella', True, 'LNA/LNB'),
            ('Stefano Doninelli', False, None),
            ('Riccardo Galfetti', False, None),
            ('Gabriele Boiani', True, '2a Lega'),
            ('Stepan Göcer', False, None),
        ],
        'I GAMB ROTT': [
            ('Alessandro Müller', True, 'Veterani'),
            ('Dewis Prior', True, '1a Lega'),
            ('Flavio Ambrosetti', False, None),
            ('Luca Lavizzari', True, 'Veterani'),
            ('Alan Giovannini', False, None),
            ('Nicole Pozzi', False, None),
            ('Mirko Pozzi', False, None),
            ('Emiliano Contini', False, None),
            ('Jari Pestelacci', False, None),
            ('Aaron Achermann', False, None),
            ('Roby Muschi', False, None),
            ('Sascha Quirici', False, None),
            ('Gualty Cimasoni', False, None),
            ('Julian Walker', False, None),
        ],
        'YELLOWSTONE': [
            ('Daniele Ponti', False, None),
            ('Daniele Bernasconi', False, None),
            ('Omar Rubbi', False, None),
            ('Colin Patchett', True, '2a Lega'),
            ('Claudio Busacchi', False, None),
            ('Luca Molone', False, None),
            ('Christian Perni', True, 'LNA/LNB'),
            ('Daniele Bernasconi', True, '1a Lega'),  # Secondo Daniele Bernasconi
            ('Alex Sala', False, None),
            ('Alessandro Motta', False, None),
            ('Andreas Brantschen', False, None),
            ('Jonny Casoni', False, None),
            ('Gianluca Braga', False, None),
        ],
        'HOCKTAIL': [
            ('Loris Griesenhofer', True, '2a Lega'),
            ('Rubina Cerutti', True, 'Femminile'),
            ('Davide Albert', True, '2a Lega'),
            ('Francesco Wezel', True, '2a Lega'),
            ('Gionata Nessi', True, '1a Lega'),
            ('Sergio Bianchi', False, None),
            ('Guillame Tagliabue', False, None),
            ('Elia Parzani', False, None),
            ('Christian Cugnetto', False, None),
            ('Michele Baggi', False, None),
            ('Aramis Rezzonico', True, '1a Lega'),
            ('Noele Zanardi', False, None),
            ('Tommaso Bernardoni', True, '1a Lega'),
            ('Daniel Arcidiacono', False, None),
        ],
        'BARDOLINO TEAM DOC': [
            ('Yannick Ruspini', True, 'LNA/LNB'),
            ('Allan Bolis', True, 'Veterani'),
            ('Carlo Briccola', True, 'LNA/LNB'),
            ('Andrea Involti', True, 'LNA/LNB'),
            ('Gianini Dennis', True, 'LNA/LNB'),
            ('Marcel Raggi', True, 'LNA/LNB'),
            ('Luca Raggi', False, None),
            ('Demian Burri', True, 'LNA/LNB'),
            ('Gabriele Curcio', True, '1a Lega'),
            ('Marcello Arnoldi', False, None),
        ],
        'ORIGINAL TWINS': [
            ('Paolo Leonardi', False, None),
            ('Andrea Leonardi', False, None),
            ('Graziano Sassi', False, None),
            ('Gabriele Amadò', False, None),
            ('Agostino Mini', False, None),
            ('Giuliano Sassi', False, None),
            ('Luca Bonfanti', False, None),
            ('Daniele Costantini', False, None),
            ('Marcel Müller', False, None),
            ('Alan Giacomini', True, 'LNA/LNB'),
            ('Michele Domeniconi', False, None),
            ('Francesco Casari', False, None),
            ('Alain Scheggia', False, None),
            ('Daniele Demarta', False, None),
            ('Nicolas Poncini', True, 'LNA/LNB'),
        ],
        'TIRABÜSCION': [
            ('Daniele Bianchi', True, '2a Lega'),
            ('Alliata Tito', False, None),
            ('Emanuele Bralla', False, None),
            ('Zdenek Jirava', False, None),
            ('Maurizio Capponi', False, None),
            ('Antonio Bianchi', False, None),
            ('Alessandra Mion', False, None),
            ('Luca Renze', False, None),
            ('Tiziano Bonoli', False, None),
            ('David Lucchini', False, None),
            ('Stefano Teggi', False, None),
            ('Alessio Demarchi', True, '2a Lega'),
            ('Michele Gambarasi', False, None),
            ('Filippo De Filippis', False, None),
            ('Samuel Spinzi', False, None),
        ],
        'FLORY MOTOS': [
            ('Adrian Schumacher', True, 'Veterani'),
            ('Andrea Guarisco', True, 'Veterani'),
            ('Patrick Ruspini', True, 'Veterani'),
            ('Aaron Bonaiti', True, 'Veterani'),
            ('Mirko Bottani', True, 'Veterani'),
            ('Patrik Arigoni', True, 'Veterani'),
            ('Eric Mercolli', False, None),
            ('Pietro Bacciarini', False, None),
            ('Giona Bacciarini', False, None),
            ('Luca Giorla', False, None),
            ('Christian Cetti', True, 'LNA/LNB'),
            ('Thomas Felappi', True, 'LNA/LNB'),
            ('Micha Tonini', False, None),
        ],
        'BARRHOCK': [
            ('Laura Bariffi', True, 'Femminile'),
            ('Serena D\'Egidio', True, 'Femminile'),
            ('Laura Desboeufs', True, 'Femminile'),
            ('Michela Sobrio', True, 'Femminile'),
            ('Tina Di Sigismondo', True, 'Femminile'),
            ('Sophie Perrenoud', True, 'Femminile'),
            ('Vasile Santini', True, 'LNA/LNB'),
            ('Simone Cavadini', False, None),
            ('Jonathan Desboeufs', True, 'LNA/LNB'),
            ('Marzio Teggi', True, 'Veterani'),
            ('Davide Tedoldi', True, 'Veterani'),
            ('Noah Triangeli', True, 'LNA/LNB'),
            ('Nicola Robbiani', True, 'Veterani'),
        ],
        'GIÜGADUU DALA LIPPA': [
            ('Elvis Ciccone', False, None),
            ('Marc Leutwyler', False, None),
            ('Teo Parini', False, None),
            ('Andreas Weber', False, None),
            ('Stefano Canepa', False, None),
            ('Alessandro Gianinazzi', False, None),
            ('Marco Franceschi', False, None),
            ('Marco Burgi', False, None),
            ('Aris Biaggi', False, None),
            ('Fiona Bleeke', False, None),
            ('Nick Frisberg', True, 'LNA/LNB'),
            ('Matteo Kaufmann', True, 'LNA/LNB'),
            ('Neno Casati', False, None),
        ],
        'LE PADELLE': [
            ('Colombo Raffaele', False, None),
            ('Lo Presti Christoph', False, None),
            ('Milani Claudia', False, None),
            ('Bosisio Sabina', False, None),
            ('Menghetti Domizia', False, None),
            ('Rossinelli Silvia', False, None),
            ('Bullo Cristina', False, None),
            ('Ruffieux Aurélie', False, None),
            ('Rossetti Noè', True, None),  # "SI" senza categoria = 2 punti
            ('Pozzi Giorgio', True, None),
            ('Santoro Fabiano', True, None),
            ('Rodriguez-Maceda Fernando', False, None),
        ],
        'PEPPA BEER': [
            ('Noahm Demarta', False, None),
            ('Kevin Schuler', False, None),
            ('Marco Cloetta', False, None),
            ('Nakia Alberti', True, 'LNA/LNB'),
            ('Luca Ferrari', False, None),
            ('Jay Regazzoni', True, 'LNA/LNB'),
            ('Matteo Cassina', True, '1a Lega'),
            ('Michele Crivelli', True, '1a Lega'),
            ('Simon Majek', False, None),
            ('Roland Majek', False, None),
            ('Elia Mazzolini', False, None),
            ('Aron Fassora', False, None),
            ('Axel Leone', True, 'LNA/LNB'),  # LNA = LNA/LNB nel sistema
        ],
        'ANIMALS TEAM': [
            ('Simone Belloni', False, None),
            ('Davide Belloni', False, None),
            ('Fabrizio Ferrazzini', False, None),
            ('Dimitri Frapolli', False, None),
            ('Enrico Strahm', False, None),
            ('Oliver Korch', False, None),
            ('Omar Bonardi', False, None),
            ('Simone Wagner', False, None),
            ('Marco Dongiovanni', False, None),
            ('Luc Bielli', False, None),
            ('Zeno Cazzoli', True, '2 lega/LNB'),
            ('Lucio Notari', False, None),
            ('Elia Ferrari', False, None),
            ('Filo Botti', False, None),
            ('Stefano Piccardo', False, None),
        ],
            'LE PADELLE': [
            ('Raffaele Colombo', False, None),
            ('Christoph Lo Presti', False, None),
            ('Claudia Milani', False, None),
            ('Sabina Bosisio', False, None),
            ('Domizia Menghetti', False, None),
            ('Silvia Rossinelli', False, None),
            ('Cristina Bullo', False, None),
            ('Aurélie Ruffieux', False, None),
            ('Noè Rossetti', True, '1a lega'),
            ('Giorgio Pozzi', True, 'LN'),
            ('Fabiano Santoro', True, 'LN'),
            ('Fernando Rodriguez-Maceda', False, None),
        ]


    }
    
    try:
        total_added = 0
        errors = []
        
        for team_name, players in players_data.items():
            team = Team.query.filter_by(name=team_name).first()
            
            if not team:
                errors.append(f"Squadra '{team_name}' non trovata")
                continue
            
            print(f"\n🏒 Aggiungendo giocatori a {team_name}...")
            
            # Elimina giocatori esistenti
            existing_count = Player.query.filter_by(team_id=team.id).count()
            if existing_count > 0:
                Player.query.filter_by(team_id=team.id).delete()
                print(f"  ❌ Rimossi {existing_count} giocatori esistenti")
            
            for name, is_registered, category in players:
                try:
                    # Crea il giocatore - I PUNTI VERRANNO CALCOLATI AUTOMATICAMENTE dal modello
                    player = Player(
                        name=name,
                        team=team,
                        is_registered=is_registered,
                        category=category
                    )
                    
                    db.session.add(player)
                    total_added += 1
                    
                    # I punti vengono calcolati automaticamente dalla proprietà registration_points
                    print(f"  ✅ {name} ({'Tesserato' if is_registered else 'Non tesserato'}, {category or 'N/A'})")
                    
                except Exception as e:
                    errors.append(f"Errore giocatore {name} in {team_name}: {str(e)}")
        
        # Salva tutto
        db.session.commit()
        
        # Ora calcola i totali usando la proprietà del modello
        teams_stats = []
        for team_name in players_data.keys():
            team = Team.query.filter_by(name=team_name).first()
            if team:
                total_points = team.player_points_total  # Questo usa la proprietà registration_points
                teams_stats.append(f"{team.name}: {len(team.players)} giocatori, {total_points} pt")
                print(f"  📊 {team.name}: {total_points} punti tesseramento")
                
                if total_points > 20:
                    errors.append(f"⚠️ {team.name} supera il limite di 20 punti ({total_points})")
        
        flash(f'🎉 Inseriti {total_added} giocatori con successo!', 'success')
        
        if errors:
            flash(f'⚠️ Errori: {"; ".join(errors)}', 'warning')
        
        flash(f'📊 Riepilogo: {" | ".join(teams_stats)}', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore: {str(e)}', 'danger')
    
    return redirect(url_for('teams'))


@app.route('/check_registration_points')
def check_registration_points():
    """Verifica i punti tesseramento di tutte le squadre."""
    teams = Team.query.all()
    
    results = []
    for team in teams:
        total_points = team.player_points_total
        status = "✅ OK" if total_points <= 20 else f"❌ LIMITE SUPERATO ({total_points}/20)"
        
        results.append(f"{team.name}: {total_points} punti {status}")
    
    flash(f"📊 Punti tesseramento: {' | '.join(results)}", 'info')
    return redirect(url_for('teams'))


# Route per esportare le classifiche in PDF
@app.route('/export_standings_pdf')
def export_standings_pdf():
    """Genera e scarica un PDF con tutte le classifiche del torneo."""
    try:
        print("🔍 Inizio generazione PDF...")
        
        # Prepara i dati come nella funzione standings()
        group_standings = get_group_standings()
        print(f"✅ Group standings caricati: {len(group_standings)} gironi")
        
        # Player statistics
        top_scorers = []
        top_assists = []
        most_penalties = []
        
        try:
            if db.inspect(db.engine).has_table('player_match_stats'):
                from sqlalchemy import func
                
                print("📊 Caricamento marcatori...")


                top_scorers_query = db.session.query(
                    Player,
                    func.sum(PlayerMatchStats.goals).label('total_goals'),
                    func.count(PlayerMatchStats.match_id).label('total_matches'),
                    func.sum(PlayerMatchStats.assists).label('total_assists')
                ).join(PlayerMatchStats).filter(
                    PlayerMatchStats.is_removed != True
                ).group_by(Player.id).having(
                    func.sum(PlayerMatchStats.goals) > 0
                ).order_by(
                    func.sum(PlayerMatchStats.goals).desc(),
                    func.count(PlayerMatchStats.match_id).asc(),
                    func.sum(PlayerMatchStats.assists).desc()
                ).limit(15)
                
                for player, total_goals, total_matches, total_assists in top_scorers_query:
                    player.display_goals = total_goals
                    player.display_matches = total_matches
                    player.display_assists_for_ranking = total_assists
                    top_scorers.append(player)
                print(f"✅ Marcatori caricati: {len(top_scorers)}")        

                
                print("📊 Caricamento assist...")
                # Assist con nuova logica
                top_assists_query = db.session.query(
                        Player,
                        func.sum(PlayerMatchStats.assists).label('total_assists'),
                        func.count(PlayerMatchStats.match_id).label('total_matches'),
                        func.sum(PlayerMatchStats.goals).label('total_goals')
                    ).join(PlayerMatchStats).filter(
                        PlayerMatchStats.is_removed != True  # <- AGGIUNTO: filtra solo giocatori non rimossi
                    ).group_by(Player.id).having(
                        func.sum(PlayerMatchStats.assists) > 0
                    ).order_by(
                        func.sum(PlayerMatchStats.assists).desc(),
                        func.count(PlayerMatchStats.match_id).asc(),
                        func.sum(PlayerMatchStats.goals).desc()
                    ).limit(15)
                            
                for player, total_assists, total_matches, total_goals in top_assists_query:
                    player.display_assists = total_assists
                    player.display_matches = total_matches
                    player.display_goals_for_ranking = total_goals
                    top_assists.append(player)
                print(f"✅ Assist caricati: {len(top_assists)}")
                
                print("📊 Caricamento penalità...")
                # Penalità
                most_penalties_query = db.session.query(
                    Player,
                    func.sum(PlayerMatchStats.penalties).label('total_penalties')
                ).join(PlayerMatchStats).group_by(Player.id).having(
                    func.sum(PlayerMatchStats.penalties) > 0
                ).order_by(func.sum(PlayerMatchStats.penalties).desc()).limit(15)
                
                for player, total_penalties in most_penalties_query:
                    player.display_penalties = total_penalties
                    most_penalties.append(player)
                print(f"✅ Penalità caricate: {len(most_penalties)}")
                    
            else:
                print("⚠️ Fallback al sistema vecchio per player stats")
                # Fallback
                top_scorers = Player.query.filter(Player.goals > 0).order_by(Player.goals.desc()).limit(15).all()
                top_assists = Player.query.filter(Player.assists > 0).order_by(Player.assists.desc()).limit(15).all()
                most_penalties = Player.query.filter(Player.penalties > 0).order_by(Player.penalties.desc()).limit(15).all()
                
                for player in top_scorers:
                    player.display_goals = player.goals
                    player.display_matches = 0
                    player.display_assists_for_ranking = player.assists
                for player in top_assists:
                    player.display_assists = player.assists  
                    player.display_matches = 0
                    player.display_goals_for_ranking = player.goals
                for player in most_penalties:
                    player.display_penalties = player.penalties
        
        except Exception as e:
            print(f"❌ Errore statistiche: {e}")
            top_scorers = []
            top_assists = []
            most_penalties = []
        
        # MVP Awards
        try:
            print("🏆 Caricamento MVP Awards...")
            best_player_awards = get_best_player_awards()
            if not best_player_awards:
                best_player_awards = []
            print(f"✅ MVP Awards caricati: {len(best_player_awards)}")
        except Exception as e:
            print(f"❌ Errore MVP awards: {e}")
            best_player_awards = []
        
        # Fair Play
        try:
            print("🤝 Caricamento Fair Play...")
            fair_play_ranking = get_fair_play_ranking()
            if not fair_play_ranking:
                fair_play_ranking = []
            print(f"✅ Fair Play caricato: {len(fair_play_ranking)}")
        except Exception as e:
            print(f"❌ Errore Fair Play: {e}")
            fair_play_ranking = []
        
        # Final Rankings
        try:
            print("🏆 Caricamento Final Rankings...")
            # Controlla se la tabella esiste e ha dati
            if db.inspect(db.engine).has_table('final_ranking'):
                final_rankings = FinalRanking.query.order_by(FinalRanking.final_position).all()
                if not final_rankings:
                    final_rankings = []
            else:
                final_rankings = []
            print(f"✅ Final Rankings caricati: {len(final_rankings)}")
        except Exception as e:
            print(f"❌ Errore Final Rankings: {e}")
            final_rankings = []
        
        # All Star Team
        try:
            print("⭐ Caricamento All Star Team...")
            selections = AllStarTeam.query.all()
            all_star_data = {
                'Tesserati': {
                    'Portiere': None,
                    'Difensore_1': None,
                    'Difensore_2': None,
                    'Attaccante_1': None,
                    'Attaccante_2': None
                },
                'Non Tesserati': {
                    'Portiere': None,
                    'Difensore_1': None,
                    'Difensore_2': None,
                    'Attaccante_1': None,
                    'Attaccante_2': None
                }
            }
            
            for selection in selections:
                category = selection.category  
                position = selection.position
                if position in all_star_data[category]:
                    all_star_data[category][position] = selection.player
            print(f"✅ All Star Team caricato: {len(selections)} selezioni")
        except Exception as e:
            print(f"❌ Errore All Star Team: {e}")
            all_star_data = {
                'Tesserati': {'Portiere': None, 'Difensore_1': None, 'Difensore_2': None, 'Attaccante_1': None, 'Attaccante_2': None},
                'Non Tesserati': {'Portiere': None, 'Difensore_1': None, 'Difensore_2': None, 'Attaccante_1': None, 'Attaccante_2': None}
            }
        
        # Genera il PDF
        print("Generazione PDF...")
        buffer = BytesIO()
        pdf_filename = generate_standings_pdf(
            buffer, 
            group_standings, 
            top_scorers, 
            top_assists, 
            most_penalties,
            best_player_awards,
            fair_play_ranking,
            final_rankings,
            all_star_data
        )
        
        buffer.seek(0)
        
        # Genera nome file con data
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Classifiche_Torneo_Amici_{date_str}.pdf"
        
        print(f"✅ PDF generato con successo: {filename}")
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"❌ ERRORE GENERALE PDF: {e}")
        import traceback
        traceback.print_exc()
        flash(f'❌ Errore nella generazione del PDF: {str(e)}', 'danger')
        return redirect(url_for('standings'))


def generate_standings_pdf(buffer, group_standings, top_scorers, top_assists, 
                          most_penalties, best_player_awards, fair_play_ranking, 
                          final_rankings, all_star_data):
    """Genera il PDF con tutte le classifiche."""
    
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    
    # Stili
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        alignment=TA_CENTER,
        textColor=colors.darkgreen
    )
    
    # Titolo principale
    story.append(Paragraph("TORNEO DEGLI AMICI DELLO SKATER", title_style))
    story.append(Paragraph("Memorial Marzio Camponovo - Classifiche Finali", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # 1. CLASSIFICHE GIRONI
    story.append(Paragraph("CLASSIFICHE GIRONI", subtitle_style))
    
    for group, teams in group_standings.items():
        story.append(Paragraph(f"Girone {group}", styles['Heading3']))
        
        # Tabella girone
        data = [['Pos', 'Squadra', 'PG', 'W', 'WOT', 'LOT', 'L', 'GF', 'GS', 'DR', 'Punti']]

        for i, team in enumerate(teams, 1):

            # CORRETTO nel PDF:
            data.append([
                str(i),
                team.name,
                str(team.group_games_played),      # ✅ Solo 3 partite qualificazione
                str(team.group_wins),   
                str(team.group_wins_overtime),   # ✅ Sconfitte overtime (1 punto)
                str(team.group_losses_overtime),   # ✅ Sconfitte overtime (1 punto)
                str(team.group_losses),            # ✅ Solo sconfitte qualificazione
                str(team.group_goals_for),         # ✅ Solo gol qualificazione
                str(team.group_goals_against),     # ✅ Solo gol qualificazione
                str(team.group_goal_difference),   # ✅ Solo diff qualificazione
                str(team.group_points)             # ✅ Solo punti qualificazione
            ])
        
        table = Table(data, colWidths=[1*cm, 4*cm, 1*cm, 1*cm, 1*cm, 1*cm, 1*cm, 1*cm, 1*cm, 1.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 15))
    
    story.append(PageBreak())
    
    # 2. CLASSIFICA MARCATORI
    if top_scorers:
        story.append(Paragraph("CLASSIFICA MARCATORI", subtitle_style))
        
        data = [['Pos', 'Giocatore', 'Squadra', 'Gol', 'PG', 'Assist']]
        for i, player in enumerate(top_scorers, 1):
            pos_icon = "1." if i == 1 else "2." if i == 2 else "3." if i == 3 else str(i)
            data.append([
                pos_icon,
                player.name,
                player.team.name,
                str(player.display_goals),
                str(getattr(player, 'display_matches', 0)),
                str(getattr(player, 'display_assists_for_ranking', 0))
            ])
        
        table = Table(data, colWidths=[1.5*cm, 4*cm, 4*cm, 1.5*cm, 1.5*cm, 1.5*cm])
        # Crea gli stili base della tabella
        base_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.green),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]
        
        # Aggiungi evidenziazione podio solo se ci sono abbastanza elementi
        if len(top_scorers) >= 3:
            base_styles.append(('BACKGROUND', (0, 1), (-1, 3), colors.gold))
        
        table.setStyle(TableStyle(base_styles))
        
        story.append(table)
        story.append(Spacer(1, 20))
    
    story.append(PageBreak())
    
    # 3. CLASSIFICA ASSIST
    if top_assists:
        story.append(Paragraph("CLASSIFICA ASSIST", subtitle_style))
        
        data = [['Pos', 'Giocatore', 'Squadra', 'Assist', 'PG', 'Gol']]
        for i, player in enumerate(top_assists, 1):
            pos_icon = "1." if i == 1 else "2." if i == 2 else "3." if i == 3 else str(i)
            data.append([
                pos_icon,
                player.name,
                player.team.name,
                str(player.display_assists),
                str(getattr(player, 'display_matches', 0)),
                str(getattr(player, 'display_goals_for_ranking', 0))
            ])
        
        table = Table(data, colWidths=[1.5*cm, 4*cm, 4*cm, 1.5*cm, 1.5*cm, 1.5*cm])
        # Crea gli stili base della tabella
        base_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]
        
        # Aggiungi evidenziazione podio solo se ci sono abbastanza elementi
        if len(top_assists) >= 3:
            base_styles.append(('BACKGROUND', (0, 1), (-1, 3), colors.lightyellow))
        
        table.setStyle(TableStyle(base_styles))
        
        story.append(table)
        story.append(Spacer(1, 20))
    
    # 4. MVP AWARDS
    if best_player_awards and len(best_player_awards) > 0:
        story.append(Paragraph("PREMI MVP DELLA PARTITA", subtitle_style))
        
        data = [['Pos', 'Giocatore', 'Squadra', 'MVP Awards']]
        for i, award_entry in enumerate(best_player_awards, 1):
            # Gestisci sia tuple che liste
            if isinstance(award_entry, (tuple, list)) and len(award_entry) >= 2:
                player, awards_count = award_entry[0], award_entry[1]
            else:
                continue  # Salta entry malformate

            pos_icon = "1." if i == 1 else "2." if i == 2 else "3." if i == 3 else str(i)
            stars = "*" * awards_count
            data.append([
                pos_icon,
                player.name,
                player.team.name,
                f"{stars} ({awards_count})"
            ])
        
        if len(data) > 1:  # Solo se ci sono dati oltre l'header
            table = Table(data, colWidths=[1.5*cm, 4*cm, 4*cm, 4*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.orange),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, 1), colors.gold) if len(data) >= 2 else ('', '', '', '')
            ]))
            
            story.append(table)
            story.append(Spacer(1, 20))
    else:
        story.append(Paragraph("PREMI MVP DELLA PARTITA", subtitle_style))
        story.append(Paragraph("Nessun premio MVP ancora assegnato.", styles['Normal']))
        story.append(Spacer(1, 20))
    
    story.append(PageBreak())
    
    # 5. CLASSIFICA FINALE
    if final_rankings and len(final_rankings) > 0:
        story.append(Paragraph("CLASSIFICA FINALE DEL TORNEO", subtitle_style))
        
        data = [['Pos', 'Squadra', 'Girone', 'Categoria', 'Premio']]
        for ranking in final_rankings:
            pos_icon = "1." if ranking.final_position == 1 else "2." if ranking.final_position == 2 else "3." if ranking.final_position == 3 else str(ranking.final_position)
            category = "Major League" if ranking.final_position <= 8 else "Beer League"
            
            if ranking.final_position == 1:
                premio = "Campione"
            elif ranking.final_position == 2:
                premio = "Vicecampione"
            elif ranking.final_position == 3:
                premio = " Terzo posto"
            elif ranking.final_position == 9:
                premio = "Campione BL"
            else:
                premio = "-"
            
            data.append([
                pos_icon,
                ranking.team.name,
                f"Girone {ranking.team.group}",
                category,
                premio
            ])
        
        # Crea gli stili base della tabella
        base_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lavender),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]
        
        # Evidenzia primi 3 solo se ci sono abbastanza elementi
        if len(final_rankings) >= 3:
            base_styles.append(('BACKGROUND', (0, 1), (-1, 3), colors.gold))
        
        table = Table(data, colWidths=[1.5*cm, 4*cm, 2*cm, 3*cm, 3*cm])
        table.setStyle(TableStyle(base_styles))
        
        story.append(table)
        story.append(Spacer(1, 20))
    else:
        story.append(Paragraph("CLASSIFICA FINALE DEL TORNEO", subtitle_style))
        story.append(Paragraph("Classifica finale non ancora disponibile. Completa tutte le finali.", styles['Normal']))
        story.append(Spacer(1, 20))
    
    story.append(PageBreak())
    
    # 6. FAIR PLAY
    if fair_play_ranking and len(fair_play_ranking) > 0:
        story.append(Paragraph("CLASSIFICA FAIR PLAY", subtitle_style))
        
        data = [['Pos', 'Squadra', 'Girone', 'Min Penalità', 'Pos Finale']]
        for i, entry in enumerate(fair_play_ranking, 1):
            try:
                pos_icon = "1." if i == 1 else "2." if i == 2 else "3." if i == 3 else str(i)
                
                # Gestisci sia dizionari che oggetti
                if isinstance(entry, dict):
                    team_name = entry['team'].name
                    team_group = entry['team'].group or 'N/A'
                    penalty_minutes = entry['penalty_minutes']
                    final_position = entry['final_position']
                    has_final_ranking = entry.get('has_final_ranking', True)
                else:
                    team_name = entry.team.name
                    team_group = entry.team.group or 'N/A'
                    penalty_minutes = entry.penalty_minutes
                    final_position = entry.final_position
                    has_final_ranking = getattr(entry, 'has_final_ranking', True)
                
                final_pos = f"{final_position}°"
                if not has_final_ranking:
                    final_pos = f"~{final_position}°*"
                
                data.append([
                    pos_icon,
                    team_name,
                    f"Girone {team_group}",
                    f"{penalty_minutes}'",
                    final_pos
                ])
            except Exception as e:
                print(f"Errore processando entry Fair Play: {e}")
                continue
        
        if len(data) > 1:  # Solo se ci sono dati oltre l'header
            # Crea gli stili base della tabella
            base_styles = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.teal),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightcyan),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]
            
            # Evidenzia primo posto solo se ci sono dati
            if len(data) >= 2:  # Header + almeno 1 riga di dati
                base_styles.append(('BACKGROUND', (0, 1), (-1, 1), colors.lightgreen))
            
            table = Table(data, colWidths=[1.5*cm, 4*cm, 2*cm, 2.5*cm, 2.5*cm])
            table.setStyle(TableStyle(base_styles))
            
            story.append(table)
            story.append(Spacer(1, 20))
        else:
            story.append(Paragraph("Nessun dato Fair Play disponibile.", styles['Normal']))
            story.append(Spacer(1, 20))
    else:
        story.append(Paragraph("CLASSIFICA FAIR PLAY", subtitle_style))
        story.append(Paragraph("Classifica Fair Play non ancora disponibile.", styles['Normal']))
        story.append(Spacer(1, 20))
    
    story.append(PageBreak())
    
    # 7. ALL STAR TEAM
    story.append(Paragraph("ALL STAR TEAM", subtitle_style))
    
    for category in ['Tesserati', 'Non Tesserati']:
        story.append(Paragraph(f"ALL STAR TEAM - {category.upper()}", styles['Heading3']))
        
        data = [['Ruolo', 'Giocatore', 'Squadra']]
        
        positions = {
            'Portiere': 'Portiere',
            'Difensore_1': 'Difensore 1',
            'Difensore_2': 'Difensore 2', 
            'Attaccante_1': 'Attaccante 1',
            'Attaccante_2': 'Attaccante 2'
        }
        
        for position, display_name in positions.items():
            player = all_star_data[category][position]
            if player:
                data.append([
                    display_name,
                    player.name,
                    player.team.name
                ])
            else:
                data.append([
                    display_name,
                    "Non selezionato",
                    "-"
                ])
        
        table = Table(data, colWidths=[3*cm, 4*cm, 5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
    
    # Footer
    story.append(Spacer(1, 30))
    story.append(Paragraph("©  Torneo degli Amici dello Skater - Memorial Marzio Camponovo", styles['Normal']))
    
    doc.build(story)
    return "classifiche_complete.pdf"

# if __name__ == '__main__':
# #PORT=5001 python3 app.py
#     with app.app_context():
#         try:
#             db.create_all()
#             # create_admin_user()
#             print("Database inizializzato con successo")
#         except Exception as e:
#             print(f"Errore inizializzazione database: {e}")
    

#     # Configurazione per Railway
#     port = int(os.environ.get('PORT', 5000))
#     debug_mode = os.environ.get('FLASK_ENV') != 'production'
#     app.run(host='0.0.0.0', port=port, debug=debug_mode)


# Aggiungi questo codice al file app.py



@app.route('/download_daily_results_pdf/<date>')
def download_daily_results_pdf(date):
    """Genera e scarica un PDF con tutti i risultati di una giornata specifica."""
    try:
        # Converte la stringa della data in oggetto datetime
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Ottieni tutte le partite della giornata
        matches = Match.query.filter_by(date=date_obj).order_by(Match.time).all()
        
        if not matches:
            flash(f'Nessuna partita trovata per il {date}', 'warning')
            return redirect(url_for('schedule'))
        
        # Crea il PDF in memoria
        buffer = io.BytesIO()
        
        # Configurazione del documento PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.5*inch
        )
        
        # Elementi del documento
        elements = []
        
        # Stili
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            textColor=colors.HexColor('#0d6efd'),
            alignment=1  # Centro
        )
        
        # Titolo del documento
        date_formatted = date_obj.strftime('%d/%m/%Y')
        day_name = get_italian_day_name(date_obj.weekday())
        
        title = f"Torneo degli Amici - Risultati del {day_name} {date_formatted}"
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 20))
        
        # Determina il tipo di giornata
        phase_counts = {}
        for match in matches:
            phase = match.phase
            if phase not in phase_counts:
                phase_counts[phase] = 0
            phase_counts[phase] += 1
        
        # Crea sezioni separate per ogni fase
        for phase in ['group', 'quarterfinal', 'semifinal', 'final']:
            phase_matches = [m for m in matches if m.phase == phase]
            if not phase_matches:
                continue
                
            # Titolo della sezione
            phase_names = {
                'group': 'QUALIFICAZIONI',
                'quarterfinal': 'QUARTI DI FINALE', 
                'semifinal': 'SEMIFINALI',
                'final': 'FINALI'
            }
            
            section_style = ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=15,
                textColor=colors.HexColor('#dc3545'),
                alignment=1
            )
            
            elements.append(Paragraph(phase_names[phase], section_style))
            
            # Dati della tabella
            if phase == 'final':
                # Per le finali, includi la lega e il piazzamento
                table_data = [
                    ['N°', 'Orario', 'Lega', 'Squadra 1', 'Squadra 2', 'Risultato', 'Piazzamento', 'Note']
                ]
                
                for match in phase_matches:
                    result = get_match_result_display(match)
                    placement = get_final_placement(match)
                    notes = get_match_notes(match)
                    
                    table_data.append([
                        str(match.get_match_number()),
                        match.time.strftime('%H:%M'),
                        match.league or 'N/A',
                        match.get_team1_display_name(),
                        match.get_team2_display_name(),
                        result,
                        placement,
                        notes
                    ])
            else:
                # Per altre fasi
                table_data = [
                    ['N°', 'Orario', 'Squadra 1', 'Squadra 2', 'Risultato', 'Note']
                ]
                
                for match in phase_matches:
                    result = get_match_result_display(match)
                    notes = get_match_notes(match)
                    
                    table_data.append([
                        str(match.get_match_number()),
                        match.time.strftime('%H:%M'),
                        match.get_team1_display_name(),
                        match.get_team2_display_name(),
                        result,
                        notes
                    ])
            
            # Crea la tabella
            if phase == 'final':
                col_widths = [0.7*inch, 0.8*inch, 0.8*inch, 1.8*inch, 1.8*inch, 1.2*inch, 1.2*inch, 1.5*inch]
            else:
                col_widths = [0.7*inch, 0.8*inch, 2.2*inch, 2.2*inch, 1.5*inch, 2.0*inch]
            
            table = Table(table_data, colWidths=col_widths)
            
            # Stile della tabella
            table_style = TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Body
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
            ])
            
            table.setStyle(table_style)
            elements.append(table)
            elements.append(Spacer(1, 20))
        
        # Footer con statistiche
        stats_data = generate_daily_stats(matches)
        if stats_data:
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.gray,
                alignment=1
            )
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(stats_data, footer_style))
        
        # Genera il PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Nome del file
        filename = f"risultati_{date}_{day_name.lower()}.pdf"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'Errore nella generazione del PDF: {str(e)}', 'error')
        return redirect(url_for('schedule'))

def get_italian_day_name(weekday):
    """Restituisce il nome del giorno in italiano."""
    days = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
    return days[weekday]

def get_match_result_display(match):
    """Restituisce il risultato della partita formattato per il PDF."""
    if not match.is_completed:
        return "Non giocata"
    
    result = f"{match.team1_score} - {match.team2_score}"
    
    # Aggiungi indicatori per overtime/rigori
    if match.overtime:
        result += " (OT)"
    elif match.shootout:
        result += " (Rig)"
    
    return result

def get_final_placement(match):
    """Restituisce il piazzamento per le partite finali."""
    if not match.is_completed:
        return "TBD"
    
    if match.league == 'Champions League':
        if 'Finale' in match.get_playoff_description().get('description', ''):
            return "1° vs 2°"
        else:
            return "3° vs 4°"
    elif match.league == 'Beer League':
        if 'Finale' in match.get_playoff_description().get('description', ''):
            return "5° vs 6°"
        else:
            return "7° vs 8°"
    
    return "N/A"

def get_match_notes(match):
    """Restituisce note aggiuntive per la partita."""
    notes = []
    
    if match.winner:
        notes.append(f"Vince: {match.winner.name}")
    
    # Aggiungi informazioni sui migliori giocatori se disponibili
    if hasattr(match, 'best_player_team1') and match.best_player_team1:
        notes.append(f"MVP {match.team1.name}: {match.best_player_team1.name}")
    if hasattr(match, 'best_player_team2') and match.best_player_team2:
        notes.append(f"MVP {match.team2.name}: {match.best_player_team2.name}")
    
    return " | ".join(notes) if notes else "-"

def generate_daily_stats(matches):
    """Genera statistiche riepilogative della giornata."""
    if not matches:
        return ""
    
    total_matches = len(matches)
    completed_matches = len([m for m in matches if m.is_completed])
    total_goals = sum((m.team1_score or 0) + (m.team2_score or 0) for m in matches if m.is_completed)
    
    overtime_matches = len([m for m in matches if m.overtime])
    shootout_matches = len([m for m in matches if m.shootout])
    
    stats = f"Partite totali: {total_matches} | Completate: {completed_matches} | "
    stats += f"Gol totali: {total_goals}"
    
    if overtime_matches > 0:
        stats += f" | Overtime: {overtime_matches}"
    if shootout_matches > 0:
        stats += f" | Rigori: {shootout_matches}"
    
    date_obj = matches[0].date
    stats += f" | Generato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
    
    return stats


@app.route('/debug_group_matches')
def debug_group_matches():
    """Debug: verifica lo stato delle partite di gruppo."""
    
    # Conta tutte le partite di gruppo
    total_group_matches = Match.query.filter_by(phase='group').count()
    
    # Conta le partite completate (con punteggi)
    completed_matches = Match.query.filter_by(phase='group').filter(
        Match.team1_score.isnot(None),
        Match.team2_score.isnot(None)
    ).count()
    
    # Conta le partite incomplete (senza punteggi)
    incomplete_matches = Match.query.filter_by(phase='group').filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).count()
    
    # Verifica la funzione principale
    all_completed = all_group_matches_completed()
    
    # Ottieni lista delle partite incomplete
    incomplete_list = Match.query.filter_by(phase='group').filter(
        Match.team1_score.is_(None) | Match.team2_score.is_(None)
    ).all()
    
    debug_info = {
        'total_group_matches': total_group_matches,
        'completed_matches': completed_matches,
        'incomplete_matches': incomplete_matches,
        'all_completed_result': all_completed,
        'incomplete_details': [
            f"Partita {m.id}: {m.team1.name if m.team1 else 'N/A'} vs {m.team2.name if m.team2 else 'N/A'} - {m.date}"
            for m in incomplete_list[:10]  # Mostra solo le prime 10
        ]
    }
    
    flash(f'🔍 Debug partite di gruppo: {debug_info}', 'info')
    return redirect(url_for('schedule'))


@app.route('/debug_group_standings')
def debug_group_standings():
    """Debug: mostra le classifiche dei gironi."""
    
    standings = {}
    for group in ['A', 'B', 'C', 'D']:
        teams = Team.query.filter_by(group=group).order_by(
            Team.points.desc(), 
            (Team.goals_for - Team.goals_against).desc(),
            Team.goals_for.desc()
        ).all()
        
        standings[group] = []
        for i, team in enumerate(teams):
            standings[group].append({
                'position': i+1,
                'name': team.name,
                'points': team.points,
                'gf': team.goals_for,
                'ga': team.goals_against,
                'diff': team.goals_for - team.goals_against
            })
    
    flash(f'📊 Classifiche gironi: {standings}', 'info')
    return redirect(url_for('schedule'))

@app.route('/test_update_playoffs_detailed')
def test_update_playoffs_detailed():
    """Test dettagliato dell'aggiornamento playoff."""
    try:
        print("🧪 INIZIO TEST AGGIORNAMENTO PLAYOFF")
        
        # 1. Verifica qualificazioni
        if not all_group_matches_completed():
            flash("❌ Qualificazioni non completate", 'danger')
            return redirect(url_for('schedule'))
        
        print("✅ Qualificazioni completate")
        
        # 2. Ottieni classifiche
        standings = {}
        for group in ['A', 'B', 'C', 'D']:
            teams = Team.query.filter_by(group=group).order_by(
                Team.points.desc(), 
                (Team.goals_for - Team.goals_against).desc(),
                Team.goals_for.desc()
            ).all()
            standings[group] = teams
            print(f"📊 Girone {group}: {[t.name for t in teams]}")
        
        # 3. Verifica che ogni girone abbia 4 squadre
        for group in ['A', 'B', 'C', 'D']:
            if len(standings[group]) < 4:
                flash(f"❌ Girone {group} ha solo {len(standings[group])} squadre!", 'danger')
                return redirect(url_for('schedule'))
        
        print("✅ Tutti i gironi hanno 4 squadre")
        
        # 4. Aggiorna i quarti di finale Major League
        ml_quarters = Match.query.filter_by(phase='quarterfinal', league='Major League').order_by(Match.time).all()
        
        # Accoppiamenti Major League: 1C vs 2D, 1B vs 2C, 1D vs 2A, 1A vs 2B
        ml_matchups = [
            (standings['D'][0], standings['C'][1]),  # 1D vs 2C
            (standings['A'][0], standings['B'][1]),  # 1A vs 2B
            (standings['C'][0], standings['A'][1]),  # 1C vs 2A
            (standings['B'][0], standings['D'][1]),  # 1B vs 2D
        ]
        
        print("🔄 Aggiornamento Major League:")
        for i, (team1, team2) in enumerate(ml_matchups):
            if i < len(ml_quarters):
                ml_quarters[i].team1_id = team1.id
                ml_quarters[i].team2_id = team2.id
                print(f"  Partita {i+1}: {team1.name} vs {team2.name}")
        
        # 5. Aggiorna i quarti di finale Beer League
        bl_quarters = Match.query.filter_by(phase='quarterfinal', league='Beer League').order_by(Match.time).all()
        
        # Accoppiamenti Beer League: 3B vs 4C, 3D vs 4A, 3A vs 4B, 3C vs 4D
        bl_matchups = [
            (standings['B'][2], standings['A'][3]),  # 3B vs 4A
            (standings['D'][2], standings['C'][3]),  # 3D vs 4C
            (standings['A'][2], standings['D'][3]),  # 3A vs 4D
            (standings['C'][2], standings['B'][3]),  # 3C vs 4B
        ]
        
        print("🔄 Aggiornamento Beer League:")
        for i, (team1, team2) in enumerate(bl_matchups):
            if i < len(bl_quarters):
                bl_quarters[i].team1_id = team1.id
                bl_quarters[i].team2_id = team2.id
                print(f"  Partita {i+1}: {team1.name} vs {team2.name}")
        
        # 6. Salva nel database
        db.session.commit()
        
        flash('🎯 Playoff aggiornati con successo! Le squadre sono state assegnate ai quarti di finale.', 'success')
        print("✅ AGGIORNAMENTO COMPLETATO")
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante l\'aggiornamento: {str(e)}', 'danger')
        print(f"❌ ERRORE: {e}")
    
    return redirect(url_for('schedule'))



@app.route('/debug_quarterfinals_status')
def debug_quarterfinals_status():
    """Debug: verifica lo stato dei quarti di finale."""
    
    # Conta i quarti di finale esistenti
    total_quarters = Match.query.filter_by(phase='quarterfinal').count()
    
    # Quarti con squadre assegnate
    quarters_with_teams = Match.query.filter_by(phase='quarterfinal').filter(
        Match.team1_id.isnot(None),
        Match.team2_id.isnot(None)
    ).count()
    
    # Quarti con squadre NULL
    quarters_with_nulls = Match.query.filter_by(phase='quarterfinal').filter(
        Match.team1_id.is_(None) | Match.team2_id.is_(None)
    ).count()
    
    # Dettagli delle partite
    quarters_details = []
    quarters = Match.query.filter_by(phase='quarterfinal').order_by(Match.league, Match.time).all()
    
    for match in quarters:
        quarters_details.append({
            'id': match.id,
            'league': match.league,
            'date': match.date,
            'time': match.time,
            'team1': match.team1.name if match.team1 else 'NULL',
            'team2': match.team2.name if match.team2 else 'NULL',
            'team1_id': match.team1_id,
            'team2_id': match.team2_id
        })
    
    debug_info = {
        'total_quarters': total_quarters,
        'quarters_with_teams': quarters_with_teams,
        'quarters_with_nulls': quarters_with_nulls,
        'quarters_details': quarters_details
    }
    
    flash(f'🏆 Debug quarti di finale: {debug_info}', 'info')
    return redirect(url_for('schedule'))

@app.route('/step_by_step_check')
def step_by_step_check():
    """Controllo passo-passo della funzione all_group_matches_completed."""
    
    print("🔍 INIZIO DEBUG all_group_matches_completed()")
    
    # Passo 1: Ottieni tutte le partite di gruppo
    group_matches = Match.query.filter_by(phase='group').all()
    print(f"📋 Trovate {len(group_matches)} partite di gruppo")
    
    # Passo 2: Controlla ogni partita
    incomplete_count = 0
    for i, match in enumerate(group_matches):
        has_score1 = match.team1_score is not None
        has_score2 = match.team2_score is not None
        is_complete = has_score1 and has_score2
        
        if not is_complete:
            incomplete_count += 1
            print(f"❌ Partita {i+1} incompleta: {match.team1.name if match.team1 else 'N/A'} ({match.team1_score}) vs {match.team2.name if match.team2 else 'N/A'} ({match.team2_score})")
        else:
            print(f"✅ Partita {i+1} completa: {match.team1.name} ({match.team1_score}) vs {match.team2.name} ({match.team2_score})")
    
    # Passo 3: Risultato della funzione
    function_result = all_group_matches_completed()
    manual_result = incomplete_count == 0
    
    print(f"🧮 Conteggio manuale partite incomplete: {incomplete_count}")
    print(f"🔧 Risultato funzione all_group_matches_completed(): {function_result}")
    print(f"👆 Risultato atteso (manual): {manual_result}")
    print(f"🎯 Match: {function_result == manual_result}")
    
    flash(f"Debug completato - Vedi console per dettagli. Incomplete: {incomplete_count}, Funzione: {function_result}", 'info')
    return redirect(url_for('schedule'))
























@app.route('/insert_test_scores', methods=['POST','GET'])
def insert_test_scores():
    """Inserisce punteggi casuali realistici nelle partite di qualificazione per test."""
    try:
        import random
        
        # Ottieni tutte le partite di qualificazione non completate
        qualification_matches = Match.query.filter_by(phase='group').filter(
            Match.team1_score.is_(None) | Match.team2_score.is_(None)
        ).all()
        
        if not qualification_matches:
            flash('Tutte le partite di qualificazione sono già state completate!', 'info')
            return redirect(url_for('schedule'))
        
        matches_updated = 0
        total_goals = 0
        overtime_matches = 0
        
        for match in qualification_matches:
            # Genera punteggi casuali realistici per l'hockey
            # Distribuzione realistica: 0-7 gol per squadra, più probabili 1-4
            weights = [5, 15, 25, 25, 15, 10, 3, 2]  # Pesi per 0-7 gol
            
            team1_score = random.choices(range(8), weights=weights)[0]
            team2_score = random.choices(range(8), weights=weights)[0]
            
            # Se finisce in pareggio, decidi se va ai supplementari (30% probabilità)
            overtime = False
            shootout = False
            
            if team1_score == team2_score and random.random() < 0.3:
                # Vai ai supplementari
                overtime = True
                
                # 60% probabilità che finisca in overtime, 40% ai rigori
                if random.random() < 0.6:
                    # Finisce in overtime - uno segna
                    if random.random() < 0.5:
                        team1_score += 1
                    else:
                        team2_score += 1
                else:
                    # Va ai rigori
                    shootout = True
                    overtime = False  # Se va ai rigori, non è tecnicamente overtime
                    if random.random() < 0.5:
                        team1_score += 1
                    else:
                        team2_score += 1
                
                overtime_matches += 1
            
            # Salva i vecchi punteggi per update_team_stats
            old_team1_score = match.team1_score
            old_team2_score = match.team2_score
            old_overtime = getattr(match, 'overtime', False)
            old_shootout = getattr(match, 'shootout', False)
            
            # Aggiorna la partita
            match.team1_score = team1_score
            match.team2_score = team2_score
            
            # Aggiorna overtime/shootout se il modello li supporta
            if hasattr(match, 'overtime'):
                match.overtime = overtime
            if hasattr(match, 'shootout'):
                match.shootout = shootout
            
            # Aggiorna le statistiche delle squadre
            update_team_stats(match, old_team1_score, old_team2_score, old_overtime, old_shootout)
            
            # Genera statistiche casuali per i giocatori
            generate_random_player_stats(match, team1_score, team2_score)
            
            matches_updated += 1
            total_goals += team1_score + team2_score
        
        db.session.commit()
        
        # Messaggio di successo con statistiche
        avg_goals = round(total_goals / matches_updated, 1) if matches_updated > 0 else 0
        message = f'🎲 Inseriti punteggi casuali in {matches_updated} partite! '
        message += f'Media gol: {avg_goals}, Supplementari/Rigori: {overtime_matches}'
        
        flash(message, 'success')
        
        # Se tutte le qualificazioni sono completate, offri di aggiornare i playoff
        if all_group_matches_completed():
            flash('✅ Tutte le qualificazioni completate! I playoff verranno aggiornati automaticamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante l\'inserimento punteggi casuali: {str(e)}', 'danger')
        import traceback
        print(f"Errore dettagliato: {traceback.format_exc()}")
    
    return redirect(url_for('schedule'))


def generate_random_player_stats(match, team1_score, team2_score):
    """Genera statistiche casuali realistiche per i giocatori di una partita."""
    try:
        # Verifica che esista la tabella PlayerMatchStats
        if not db.inspect(db.engine).has_table('player_match_stats'):
            return
        
        # Ottieni i giocatori di entrambe le squadre
        team1_players = list(match.team1.players) if match.team1 else []
        team2_players = list(match.team2.players) if match.team2 else []
        
        if not team1_players or not team2_players:
            return
        
        # Distribuisci i gol di team1
        distribute_goals_randomly(team1_players, team1_score, match.id)
        
        # Distribuisci i gol di team2  
        distribute_goals_randomly(team2_players, team2_score, match.id)
        
        # Aggiungi assist e penalità per tutti i giocatori
        add_random_assists_and_penalties(team1_players + team2_players, match.id, team1_score + team2_score)
        
        # Seleziona MVP casuali
        select_random_mvps(team1_players, team2_players, match.id)
        
    except Exception as e:
        print(f"Errore nella generazione statistiche giocatori: {e}")


def distribute_goals_randomly(players, total_goals, match_id):
    """Distribuisce i gol casualmente tra i giocatori di una squadra."""
    import random
    
    if total_goals == 0 or not players:
        # Crea record vuoti anche se non ci sono gol
        for player in players:
            create_empty_player_stats(player.id, match_id)
        return
    
    # Lista dei giocatori che possono ancora segnare (max 3 gol a testa)
    available_players = players.copy()
    goals_per_player = {player.id: 0 for player in players}
    
    # Distribuisci i gol uno per uno
    for _ in range(total_goals):
        if not available_players:
            break
            
        # Scegli un marcatore casuale
        scorer = random.choice(available_players)
        goals_per_player[scorer.id] += 1
        
        # Se ha raggiunto il massimo (3 gol), rimuovilo dalla lista
        if goals_per_player[scorer.id] >= 3:
            available_players.remove(scorer)
    
    # Crea/aggiorna le statistiche per tutti i giocatori
    for player in players:
        goals = goals_per_player[player.id]
        update_or_create_player_match_stats(
            player.id, match_id, 
            goals=goals, assists=0, penalties=0
        )


def add_random_assists_and_penalties(all_players, match_id, total_goals):
    """Aggiunge assist e penalità casuali a tutti i giocatori."""
    import random
    
    for player in all_players:
        # Ottieni gol attuali del giocatore
        existing_stats = get_existing_player_stats(player.id, match_id)
        current_goals = existing_stats.get('goals', 0) if existing_stats else 0
        
        # Calcola assist (più probabili per chi non ha segnato)
        assists = 0
        if current_goals == 0:
            # Giocatori senza gol: 25% probabilità di 1-2 assist
            if random.random() < 0.25:
                assists = random.randint(1, 2)
        else:
            # Giocatori con gol: 15% probabilità di 1 assist
            if random.random() < 0.15:
                assists = 1
        
        # Calcola penalità (rare: 8% probabilità)
        penalty_duration = 0
        if random.random() < 0.08:
            # Tipo di penalità più comuni in minuti
            penalty_types = [2, 2, 2, 2, 5, 10]  # Più probabili le minori
            penalty_duration = random.choice(penalty_types)
        
        # Aggiorna le statistiche
        update_or_create_player_match_stats(
            player.id, match_id,
            goals=current_goals, assists=assists, penalties=penalty_duration
        )


def select_random_mvps(team1_players, team2_players, match_id):
    """Seleziona MVP casuali per entrambe le squadre."""
    import random
    
    # Preferisci giocatori con statistiche migliori per MVP
    def get_player_score(player_id):
        stats = get_existing_player_stats(player_id, match_id)
        if not stats:
            return 0
        return (stats.get('goals', 0) * 3) + (stats.get('assists', 0) * 2) - (stats.get('penalties', 0) * 0.5)
    
    # MVP Team 1
    if team1_players:
        # 70% probabilità di scegliere il migliore, 30% casuale
        if random.random() < 0.7:
            mvp1 = max(team1_players, key=lambda p: get_player_score(p.id))
        else:
            mvp1 = random.choice(team1_players)
        
        update_mvp_status(mvp1.id, match_id, is_team1=True)
    
    # MVP Team 2
    if team2_players:
        if random.random() < 0.7:
            mvp2 = max(team2_players, key=lambda p: get_player_score(p.id))
        else:
            mvp2 = random.choice(team2_players)
        
        update_mvp_status(mvp2.id, match_id, is_team2=True)


def create_empty_player_stats(player_id, match_id):
    """Crea statistiche vuote per un giocatore."""
    update_or_create_player_match_stats(player_id, match_id, goals=0, assists=0, penalties=0)


def update_or_create_player_match_stats(player_id, match_id, goals=0, assists=0, penalties=0):
    """Crea o aggiorna le statistiche di un giocatore per una partita."""
    try:
        existing_stats = PlayerMatchStats.query.filter_by(
            player_id=player_id, match_id=match_id
        ).first()
        
        if existing_stats:
            existing_stats.goals = goals
            existing_stats.assists = assists
            existing_stats.penalties = penalties
        else:
            new_stats = PlayerMatchStats(
                player_id=player_id,
                match_id=match_id,
                goals=goals,
                assists=assists,
                penalties=penalties,
                is_best_player_team1=False,
                is_best_player_team2=False
            )
            db.session.add(new_stats)
    except Exception as e:
        print(f"Errore aggiornamento statistiche giocatore {player_id}: {e}")


def get_existing_player_stats(player_id, match_id):
    """Ottieni le statistiche esistenti di un giocatore per una partita."""
    try:
        stats = PlayerMatchStats.query.filter_by(
            player_id=player_id, match_id=match_id
        ).first()
        
        if stats:
            return {
                'goals': stats.goals,
                'assists': stats.assists,
                'penalties': stats.penalties
            }
    except Exception as e:
        print(f"Errore recupero statistiche giocatore {player_id}: {e}")
    
    return None


def update_mvp_status(player_id, match_id, is_team1=False, is_team2=False):
    """Aggiorna lo status MVP di un giocatore."""
    try:
        stats = PlayerMatchStats.query.filter_by(
            player_id=player_id, match_id=match_id
        ).first()
        
        if stats:
            if is_team1:
                stats.is_best_player_team1 = True
            if is_team2:
                stats.is_best_player_team2 = True
    except Exception as e:
        print(f"Errore aggiornamento MVP per giocatore {player_id}: {e}")


# Route per resettare solo i punteggi (mantenendo il calendario)
@app.route('/reset_scores_only', methods=['POST'])
def reset_scores_only():
    """Resetta solo i punteggi delle qualificazioni, mantenendo il calendario."""
    try:
        # Reset punteggi partite di gruppo
        group_matches = Match.query.filter_by(phase='group').all()
        matches_reset = 0
        
        for match in group_matches:
            if match.is_completed:
                match.team1_score = None
                match.team2_score = None
                if hasattr(match, 'overtime'):
                    match.overtime = False
                if hasattr(match, 'shootout'):
                    match.shootout = False
                matches_reset += 1
        
        # Reset statistiche squadre
        teams = Team.query.all()
        for team in teams:
            team.wins = 0
            team.losses = 0
            team.draws = 0
            team.goals_for = 0
            team.goals_against = 0
            team.points = 0
        
        # Reset statistiche giocatori per partita
        if db.inspect(db.engine).has_table('player_match_stats'):
            PlayerMatchStats.query.filter(
                PlayerMatchStats.match_id.in_([m.id for m in group_matches])
            ).delete(synchronize_session=False)
        
        # Reset playoff teams a NULL
        playoff_matches = Match.query.filter(Match.phase != 'group').all()
        for match in playoff_matches:
            match.team1_id = None
            match.team2_id = None
            match.team1_score = None
            match.team2_score = None
            if hasattr(match, 'overtime'):
                match.overtime = False
            if hasattr(match, 'shootout'):
                match.shootout = False
        
        db.session.commit()
        
        flash(f'🔄 Resettati i punteggi di {matches_reset} partite di qualificazione!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Errore durante il reset: {str(e)}', 'danger')
    
    return redirect(url_for('schedule'))






if __name__ == '__main__':
    #PORT=5001 python3 app.py
    with app.app_context():
        try:
            db.create_all()
            print("Database inizializzato con successo")
            
            # In sviluppo, crea utente admin di default
            if not os.environ.get('RAILWAY_ENVIRONMENT'):
                admin_user = User.query.filter_by(username='admin').first()
                if not admin_user:
                    admin_user = User(username='admin', role='admin')
                    admin_user.set_password('admin123')
                    db.session.add(admin_user)
                    db.session.commit()
                    print("Utente admin creato (username: admin, password: admin123)")
        except Exception as e:
            print(f"Errore inizializzazione database: {e}")
    
    # Configurazione per Railway
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)