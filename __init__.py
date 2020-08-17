from flask import Flask, render_template, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from flask import request
from wtforms import StringField, SelectField, FileField, MultipleFileField, SelectMultipleField, DateField
from wtforms.validators import InputRequired, Email, Length, AnyOf
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_user import current_user, login_required, roles_required, UserManager, UserMixin
from flask_babelex import Babel
from flask_nav import Nav, register_renderer
from flask_nav.elements import *
from flask_bootstrap.nav import BootstrapRenderer
from flask_uploads import UploadSet, configure_uploads, IMAGES, TEXT, DOCUMENTS, DATA,All
from dominate import tags
import datetime
import json
import os
import smtplib
import ssl
from email.mime.text import MIMEText

app_name = '4D BIM'
projects = {}
software_names = ['Synchro Pro', 'Asta PowerProject', 'Navisworks Manage']
base_dir = os.path.dirname(__file__)

#
# Class-based application configuration
class ConfigClass(object):
    """ Flask application config """

    # Flask settings
    SECRET_KEY = 'Damien.Kavanagh.aec.services'

    # Flask-SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = 'sqlite:///users.sqlite'    # File-based SQL database
    SQLALCHEMY_TRACK_MODIFICATIONS = False    # Avoids SQLAlchemy warning

    # Flask-User settings
    USER_APP_NAME = app_name      # Shown in and email templates and page footers
    USER_ENABLE_EMAIL = False        # Disable email authentication
    USER_ENABLE_USERNAME = False    # Enable username authentication
    # USER_ENABLE_CONFIRM_EMAIL = False
    # USER_SEND_REGISTERED_EMAIL = False
    # USER_AFTER_REGISTER_ENDPOINT = 'user.login'
    USER_AFTER_LOGIN_ENDPOINT = 'recommend'

    USER_EMAIL_SENDER_NAME = USER_APP_NAME
    USER_EMAIL_SENDER_EMAIL = "noreply@example.com"

    UPLOADED_IMAGES_DEST = base_dir + '/static/upload/img'
    UPLOADED_FILES_DEST = base_dir + '/static/upload/file'


# Create Flask app load app.config
app = Flask(__name__)
app.config.from_object(__name__ + '.ConfigClass')

# Initialize Flask-BabelEx
babel = Babel(app)

db = SQLAlchemy(app)

#
# Define the User data-model.
# NB: Make sure to add flask_user UserMixin !!!


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column('is_active', db.Boolean(),
                       nullable=False, server_default='1')

    # User authentication information. The collation='NOCASE' is required
    # to search case insensitively when USER_IFIND_MODE is 'nocase_collation'.
    email = db.Column(db.String(255, collation='NOCASE'),
                      nullable=False, unique=True)
    email_confirmed_at = db.Column(db.DateTime())
    password = db.Column(db.String(255), nullable=False, server_default='')

    # User information
    first_name = db.Column(db.String(100, collation='NOCASE'),
                           nullable=False, server_default='')
    last_name = db.Column(db.String(100, collation='NOCASE'),
                          nullable=False, server_default='')

    # Define the relationship to Role via UserRoles
    roles = db.relationship('Role', secondary='user_roles')


# Define the Role data-model
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)


# Define the UserRoles association table
class UserRoles(db.Model):
    __tablename__ = 'user_roles'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey(
        'users.id', ondelete='CASCADE'))
    role_id = db.Column(db.Integer(), db.ForeignKey(
        'roles.id', ondelete='CASCADE'))


# Setup Flask-User and specify the User data-model
user_manager = UserManager(app, db, User)

# Create all database tables
db.create_all()

# Create 'admin@example.com' user with 'Admin' and 'Agent' roles
if not User.query.filter(User.email == 'damien.kavanagh.aec.services@gmail.com').first():
    user = User(
        email='damien.kavanagh.aec.services@gmail.com',
        email_confirmed_at=datetime.datetime.utcnow(),
        password=user_manager.hash_password('adminpassword'),
        first_name='',
        last_name=''
    )
    user.roles.append(Role(name='Admin'))
    user.roles.append(Role(name='Expert'))
    db.session.add(user)
    db.session.commit()


def proximity(pA, pB):
    """
    INPUT: two project vectors pA and pB
    OUTPUT: a real number measuring the distance between
    them.
    NOTES: We can play around with different
    distance functions to see which is more suitable.
    """
    n = len(pA)
    return sum((1 - abs(a - b)) for a, b in zip(pA, pB)) / n


def nearest_neighbours(p, old_projects):
    """
    INPUT: p - a project vector, oldprojects - a list of tuples (project vector, software choice) [here software choice is a number in {1, 2, 3} representing the choice of software.
    OUTPUT: a list of the projects in oldprojects which most closely resemble
    our project of interest.
    NOTES: We can add a variable called threshold which controls the number of
    projects in our output - this could be either the maximum number of such projects, a ratio of the total number of projects, or a limit on the maximum distance.
    """
    threshold = 5
    return sorted(old_projects, key=lambda proj: proximity(p, proj[0]), reverse=True)[:threshold]


def software_choice2(p, old_projects):
    """
    INPUT: p - a project vector
    OUTPUT: a number in {0, 1, 2} indicating the project choice.
    NOTES:
    """
    scores = [0, 0, 0]

    for proj, soft in nearest_neighbours(p, old_projects):
        scores[soft - 1] = scores[soft - 1] + proximity(p, proj)

    return scores


def max_score(lst):
    ind, score = max(enumerate(lst), key=lambda x: x[1])
    return ind, score


def load_projects():
    global projects
    if os.path.exists(base_dir + '/projects.json'):
        with open(base_dir + '/projects.json', 'r') as fp:
            projects = json.load(fp)


def save_projects():
    global projects
    with open(base_dir + '/projects.json', 'w') as fp:
        json.dump(projects, fp)


def compare_list(a, b):
    print(a)
    print(b)
    similarities = 0
    for i in range(len(a)):
        if a[i] == b[i]:
            similarities = similarities +1
    print(similarities)
    return similarities


class NoValidationSelectField(SelectField):
    def pre_validate(self, form):
        """per_validation is disabled"""


class NoValidationSelectMultipleField(SelectMultipleField):
    def pre_validate(self, form):
        """per_validation is disabled"""


class ProjectForm(FlaskForm):
    title = StringField('Project Title & Organization', validators=[
                        InputRequired()], render_kw={'autocomplete': 'nothing'})
    organisation_url = StringField('Organization URL', render_kw={
                                   'autocomplete': 'nothing'})
    country = StringField('Country', render_kw={'autocomplete': 'nothing'})
    city = StringField('City', render_kw={'autocomplete': 'nothing'})
    local_authority = StringField('Local Authority', render_kw={
                                  'autocomplete': 'nothing'})
    involvement = StringField('Individual Project Involvement', validators=[
                              InputRequired()], render_kw={'autocomplete': 'nothing'})
    date_of_project = DateField('Date of Project Completion', id='date_of_project',
                                format='%Y-%m-%d', validators=[InputRequired()], render_kw={'autocomplete': 'nothing'})
    application = SelectField('4D Software Application Used', choices=[(ind, software_names[ind]) for ind in range(
        len(software_names))], coerce=int, render_kw={'autocomplete': 'nothing'})
    version = StringField('Software Application Version', validators=[
                          InputRequired()], render_kw={'autocomplete': 'nothing'})
    award = StringField('Specific Project defined Award(s) won',
                        render_kw={'autocomplete': 'nothing'})
    email = StringField(
        'E-mail', validators=[InputRequired(), Email(message='I don\'t like your email.')])

    def reset(self):
        blank_data = {'csrf': self.csrf_token}
        self.process(blank_data)


class ScoreForm(FlaskForm):
    title = StringField('Project Title & Organization',
                        render_kw={'readonly': True})
    organisation_url = StringField(
        'Organization URL', render_kw={'readonly': True})
    country = StringField('Country', render_kw={'readonly': True})
    city = StringField('City', render_kw={'readonly': True})
    local_authority = StringField(
        'Local Authority', render_kw={'readonly': True})
    involvement = StringField(
        'Individual Project Involvement', render_kw={'readonly': True})
    date_of_project = DateField('Date of Project Completion', id='date_of_project',
                                format='%Y-%m-%d', render_kw={'readonly': True})
    application = NoValidationSelectField('4D Software Application Used', choices=[(ind, software_names[ind]) for ind in range(
        len(software_names))], coerce=int, render_kw={'readonly': True, 'disabled': True})
    version = StringField('Software Application Version',
                          render_kw={'readonly': True})
    award = StringField('Specific Project defined Award(s) won',
                        render_kw={'readonly': 'true'})
    email = StringField('E-mail', render_kw={'readonly': True})

    cm_restriction1 = SelectField('Sector type', choices=[(
        0, 'Private'), (1, 'PPP'), (2, 'Public')], coerce=int)
    cm_restriction2 = SelectField('Site logistics', choices=[(
        0, 'Little or no restriction'), (1, 'Restricted'), (2, 'Severely restricted')], coerce=int)
    cm_restriction3 = SelectField('Project duration', choices=[(
        0, '5 + Years'), (1, '2 - 5 Years'), (2, '0 - 2 Years')], coerce=int)


    cm_restriction7 = SelectField('Development use', choices=[(
        0, 'Commercial'), (1, 'Industrial'), (2, 'Ohter')], coerce=int)
    cm_restriction8 = SelectField('Financial cost of project', choices=[(
        0, '$0-10 million'), (1, '$10-50 million'), (2, '$50+ million')], coerce=int)
    cm_restriction9 = SelectField('Resource restrictions', choices=[(0, 'Restricted control of supply chain'), (
        1, 'Sufficient control of supply chain'), (2, 'Total control of supply chain')], coerce=int)


    cm_restriction4 = SelectField('Procurement method',
                                  choices=[(0, 'Fixed price'), (1, 'Design & build'), (2, 'Other')], coerce=int)
    cm_restriction5 = SelectField('Technical complexity',
                                  choices=[
                                      (0, 'Standard'), (1, 'Degree of complexity'), (2, 'Technically challenging')],
                                  coerce=int)
    cm_restriction6 = SelectField('COST Carbon footprint', choices=[(0, 'Environmental issues'), (1, 'Sustainable'), (2, 'Green')],
                                  coerce=int)

    cm_restriction6_before_files = NoValidationSelectMultipleField(
        'Select files to remove', choices=[], coerce=int)
    cm_restriction6_files = MultipleFileField(
        'Project Constraints Data and/or Images file upload')

    attribute1 = SelectField('Schedule vs actual (WIP)', choices=[
                             (x, str(x)) for x in range(11)], coerce=int)
    attribute2 = SelectField('Discreet event simulation', choices=[
                             (x, str(x)) for x in range(11)], coerce=int)
    attribute3 = SelectField('Schedule creation/manipulation',
                             choices=[(x, str(x)) for x in range(11)], coerce=int)




    attribute7 = SelectField('Simulation', choices=[(
        x, str(x)) for x in range(1, 11, 1)], coerce=int)
    attribute8 = SelectField('Clash detection', choices=[(
        x, str(x)) for x in range(1, 11, 1)], coerce=int)
    attribute9 = SelectField('Collaboration', choices=[(
        x, str(x)) for x in range(1, 11, 1)], coerce=int)



    attribute4 = SelectField('Risk assessment', choices=[
                             (x, str(x)) for x in range(11)], coerce=int)
    attribute5 = SelectField('Data analysis', choices=[(
        x, str(x)) for x in range(1, 11, 1)], coerce=int)
    attribute6 = SelectField('Construction Supply Chain Management(CSCM)', choices=[
                             (x, str(x)) for x in range(1, 11, 1)], coerce=int)



    attribute9_before_files = NoValidationSelectMultipleField(
      'Select files to remove', choices=[], coerce=int)
    attribute9_files = MultipleFileField(
      'Project Based 4D BIM Attributes Data and/or Images file upload')

    project_before_files = NoValidationSelectMultipleField(
        'Select files to remove', choices=[], coerce=int)
    project_files = MultipleFileField('Project Details Data and/or Images files upload')

    def reset(self):
        blank_data = {'csrf': self.csrf_token}
        self.process(blank_data)


class RecommendForm(FlaskForm):
    cm_restriction1 = SelectField('Sector type', choices=[(
        0, 'Private'), (1, 'Public Private Partnership (PPP)'), (2, 'Public')], coerce=int)
    cm_restriction2 = SelectField('Site logistics', choices=[(
        0, 'Little or no restriction'), (1, 'Restricted'), (2, 'Severely restricted')], coerce=int)
    cm_restriction3 = SelectField('Project duration', choices=[(
        0, '5 + Year'), (1, '2 - 5 Years'), (2, '0 - 2 Years')], coerce=int)
    cm_restriction6 = SelectField('Development use', choices=[(
        0, 'Commercial'), (1, 'Industrial'), (2, 'Other')], coerce=int)
    #cm_restriction10 = StringField('Resource control description', render_kw={'hidden': 'true'})
    cm_restriction5 = SelectField('Financial cost of project', choices=[(
        0, '$50 + million'), (1, '$10 - 50 million'), (2, '$0 - 10 million')], coerce=int)
    cm_restriction7 = SelectField('Resource restrictions', choices=[(0, 'Total control of supply chain'), (
        1, 'Sufficient control of supply chain'), (2, 'Restricted control of supply chain')], coerce=int)
    cm_restriction4 = SelectField('Procurement method', choices=[(
        0, 'Fixed price'), (1, 'Design & bulid'), (2, 'Other')], coerce=int)
    cm_restriction8 = SelectField('Technical  complexity', choices=[(0, 'Technically challenging'), (1, 'Degree of complexity'), (2, 'Standard')],
                                  coerce=int)
    cm_restriction9 = SelectField('Carbon footprint',
                                  choices=[(0, 'Green'), (1, 'Sustainable'),
                                           (2, 'Environmental issues')],
                                  coerce=int)

    country = StringField('Country', render_kw={'autocomplete': 'nothing'})
    city = StringField('City', render_kw={'autocomplete': 'nothing'})
    local_authority = StringField('Local Authority', render_kw={
                                  'autocomplete': 'nothing'})

    def reset(self):
        blank_data = {'csrf': self.csrf_token}
        self.process(blank_data)


class UserAdminForm(FlaskForm):
    email = StringField('E-mail')
    first_name = StringField('First Name', render_kw={
                             'autocomplete': 'nothing'})
    last_name = StringField('Last Name', render_kw={'autocomplete': 'nothing'})
    roles = NoValidationSelectMultipleField('Roles', choices=[], coerce=int)

    def reset(self):
        blank_data = {'csrf': self.csrf_token}
        self.process(blank_data)


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')


# @app.route('/index_1')
# def index_1():
#    return render_template('index_1.html')


@app.route('/website-design/introduction')
def introduction():
    return render_template('introduction.html')


@app.route('/website-design/design')
def instruction():
    return render_template('instruction.html')


@app.route('/successful-construction-management/4d-bim-and-added-value')
def management():
    return render_template('management.html')


@app.route('/successful-construction-management/risk-mitigation')
def risk_mitigation():
    return render_template('risk_mitigation.html')


@app.route('/successful-construction-management/exemplar-aspects-of-evaluation')
def exemplar_aspect():
    return render_template('exemplar_aspect.html')


@app.route('/best-practice-4d-bim/best-practice-evaluation')
def bim_tool():
    return render_template('bim_tool.html')


@app.route('/best-practice-4d-bim/explained')
def explained():
    return render_template('explained.html')


@app.route('/best-practice-4d-bim/project-constraints')
def constraints():
    return render_template('constraints.html')


@app.route('/best-practice-4d-bim/4d-bim-attributes')
def attributes():
    return render_template('attributes.html')


@app.route('/best-practice-4d-bim/planned-outputs')
def planned_output():
    return render_template('planned_output.html')


@app.route('/decision-support-system/add-project', methods=['GET', 'POST'])
def add():
    form = ProjectForm()
    load_projects()
    if request.method == 'GET' and current_user.is_authenticated:
        form.email.data = current_user.email
    if request.method == 'POST' and form.validate_on_submit():
        max_id = 0
        if len(projects) != 0:
            max_id = max([int(x['id']) for x in projects.values()])
        projects[max_id + 1] = {
            'id': str(max_id + 1),
            'email': form.email.data,
            'title': form.title.data,
            'organisation_url': form.organisation_url.data,
            'involvement': form.involvement.data,
            'application': form.application.data,
            'country': form.country.data,
            'city': form.city.data,
            'local_authority': form.local_authority.data,
            'version': form.version.data,
            'awards': form.award.data,
            'date_of_project': form.date_of_project.data.strftime('%Y-%m-%d'),
            'accepted': False,
            'history': False,
            'scored': False,
            'cm_restrictions': [0, 0, 0, 0, 0, 0, 0, 0, 0],
            'attribute_ratings': [0, 0, 0, 0, 0, 0, 0, 0, 0],
            'images': [],
            'project_files': [],
            'project_c_time_files': [],
            'project_c_cost_files': [],
            'project_c_quality_files': [],
        }
        save_projects()
        users = User.query.all()
        if len([x for x in users if x.email.lower() == form.email.data.lower()]) == 0:
            roles = Role.query.all()
            user = User(
                email=form.email.data,
                email_confirmed_at=datetime.datetime.utcnow(),
                password=user_manager.hash_password('123456'),
                first_name="",
                last_name=""
            )
            db.session.add(user)
            db.session.commit()
        send_email("4dbimdecisions@gmail.com", projects[max_id + 1])

        form.reset()
        return render_template('add.html',
                               form=form,
                               info='Project successfully registered!')
    return render_template('add.html',
                           form=form,
                           info=None)


images = UploadSet('images', IMAGES)
files = UploadSet('files', All())
configure_uploads(app, [images, files])


@app.route('/decision-support-system/score-projects/<int:project_id>', methods=['GET', 'POST'])
@roles_required('Expert')
def score(project_id):

    is_expert = len(
        [role for role in current_user.roles if role.name == 'Expert']) > 0
    is_admin = len(
        [role for role in current_user.roles if role.name == 'Admin']) > 0

    if project_id == 0:
        project_id = None
    if project_id is not None:
        project_id = str(project_id)
        project_id = str(project_id)
    form = ScoreForm()
    load_projects()
    try:
        is_history = projects[project_id]['history']
    except (TypeError, KeyError):
        is_history = False

    if is_history:
        form.cm_restriction1.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction2.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction3.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction4.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction5.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction6.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction7.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction8.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction9.render_kw = {'readonly': True, 'disabled': True}
        form.attribute1.render_kw = {'readonly': True, 'disabled': True}
        form.attribute2.render_kw = {'readonly': True, 'disabled': True}
        form.attribute3.render_kw = {'readonly': True, 'disabled': True}
        form.attribute4.render_kw = {'readonly': True, 'disabled': True}
        form.attribute5.render_kw = {'readonly': True, 'disabled': True}
        form.attribute6.render_kw = {'readonly': True, 'disabled': True}
        form.attribute7.render_kw = {'readonly': True, 'disabled': True}
        form.attribute8.render_kw = {'readonly': True, 'disabled': True}
        form.attribute9.render_kw = {'readonly': True, 'disabled': True}
        form.project_before_files.render_kw = {'readonly': True, 'disabled': True}
        form.project_files.render_kw = {'readonly': True, 'disabled': True}
        form.project_before_files.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction6_before_files.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction6_files.render_kw = {'readonly': True, 'disabled': True}
        form.attribute9_before_files.render_kw = {'readonly': True, 'disabled': True}
        form.attribute9_files.render_kw = {'readonly': True, 'disabled': True}


    if request.method == 'GET':
        if project_id is not None:
            form.title.data = projects[project_id]['title']
            form.organisation_url.data = projects[project_id]['organisation_url']
            form.country.data = projects[project_id]['country']
            form.city.data = projects[project_id]['city']
            form.local_authority.data = projects[project_id]['local_authority']
            form.involvement.data = projects[project_id]['involvement']
            form.date_of_project.data = datetime.datetime.strptime(
                projects[project_id]['date_of_project'], "%Y-%m-%d").date()
            form.application.data = projects[project_id]['application']
            form.version.data = projects[project_id]['version']
            try:
                form.award.data = projects[project_id]['awards']
            except:
                form.award.data = ""
            form.email.data = projects[project_id]['email']
            form.cm_restriction1.data = projects[project_id]['cm_restrictions'][0]
            form.cm_restriction2.data = projects[project_id]['cm_restrictions'][1]
            form.cm_restriction3.data = projects[project_id]['cm_restrictions'][2]
            form.cm_restriction4.data = projects[project_id]['cm_restrictions'][3]
            form.cm_restriction5.data = projects[project_id]['cm_restrictions'][4]
            form.cm_restriction6.data = projects[project_id]['cm_restrictions'][5]
            form.cm_restriction7.data = projects[project_id]['cm_restrictions'][6]
            form.cm_restriction8.data = projects[project_id]['cm_restrictions'][7]
            form.cm_restriction9.data = projects[project_id]['cm_restrictions'][8]
            form.attribute1.data = projects[project_id]['attribute_ratings'][0]
            form.attribute2.data = projects[project_id]['attribute_ratings'][1]
            form.attribute3.data = projects[project_id]['attribute_ratings'][2]
            form.attribute4.data = projects[project_id]['attribute_ratings'][3]
            form.attribute5.data = projects[project_id]['attribute_ratings'][4]
            form.attribute6.data = projects[project_id]['attribute_ratings'][5]
            form.attribute7.data = projects[project_id]['attribute_ratings'][6]
            form.attribute8.data = projects[project_id]['attribute_ratings'][7]
            form.attribute9.data = projects[project_id]['attribute_ratings'][8]
            #  Preparing delete files list

            try:
                form.project_before_files.choices = [(x, projects[project_id]['project_files'][x]) for x in range(
                    len(projects[project_id]['project_files']))]
            except  KeyError:
                projects[project_id]['project_files'] = []

            try:
                form.cm_restriction6_before_files.choices = [(x, projects[project_id]['cm_restriction6_files'][x]) for x in range(
                    len(projects[project_id]['cm_restriction6_files']))]
            except  KeyError:
                projects[project_id]['cm_restriction6_files'] = []

            try:
                form.attribute9_before_files.choices = [(x, projects[project_id]['attribute9_files'][x]) for x in range(
                    len(projects[project_id]['attribute9_files']))]
            except  KeyError:
                projects[project_id]['attribute9_files'] = []

    if request.method == 'POST' and form.validate_on_submit():
        projects[project_id].update({
            'cm_restrictions': [form.cm_restriction1.data,
                                form.cm_restriction2.data,
                                form.cm_restriction3.data,
                                form.cm_restriction4.data,
                                form.cm_restriction5.data,
                                form.cm_restriction6.data,
                                form.cm_restriction7.data,
                                form.cm_restriction8.data,
                                form.cm_restriction9.data],
            'attribute_ratings': [form.attribute1.data,
                                  form.attribute2.data,
                                  form.attribute3.data,
                                  form.attribute4.data,
                                  form.attribute5.data,
                                  form.attribute6.data,
                                  form.attribute7.data,
                                  form.attribute8.data,
                                  form.attribute9.data]
        })


        # project  files
        for ind in form.project_before_files.data[::-1]:
            os.remove(base_dir + '/static/upload/file/' +
                      projects[project_id]['project_files'][ind])
            del projects[project_id]['project_files'][ind]

        project_filenames = []

        for item in request.files.getlist('project_files'):
            if item:
                project_filenames.append(files.save(item))

        try:
            projects[project_id]['project_files'] += project_filenames
        except KeyError:
            projects[project_id]['project_files'] = project_filenames


        # project constraints  files
        for ind in form.cm_restriction6_before_files.data[::-1]:
            os.remove(base_dir + '/static/upload/file/' +
                      projects[project_id]['cm_restriction6_files'][ind])
            del projects[project_id]['cm_restriction6_files'][ind]

        cm_restriction6_files = []

        for item in request.files.getlist('cm_restriction6_files'):
            if item:
                cm_restriction6_files.append(files.save(item))

        try:
            projects[project_id]['cm_restriction6_files'] += cm_restriction6_files
        except KeyError:
            projects[project_id]['cm_restriction6_files'] = cm_restriction6_files


        # project Attributes (Section 2) COST Files
        for ind in form.attribute9_before_files .data[::-1]:
            os.remove(base_dir + '/static/upload/file/' +
                      projects[project_id]['attribute9_files'][ind])
            del projects[project_id]['attribute9_files'][ind]

        attribute9_files = []

        for item in request.files.getlist('attribute9_files'):
            if item:
                attribute9_files.append(files.save(item))

        try:
            projects[project_id]['attribute9_files'] += attribute9_files
        except KeyError:
            projects[project_id]['attribute9_files'] = attribute9_files


        # End Project files

        save_projects()

        form.project_before_files.choices = [(x, projects[project_id]['project_files'][x]) for x in range(
            len(projects[project_id]['project_files']))]
        form.cm_restriction6_before_files.choices = [(x, projects[project_id]['cm_restriction6_files'][x]) for x in range(
            len(projects[project_id]['cm_restriction6_files']))]

        form.attribute9_before_files.choices = [(x, projects[project_id]['attribute9_files'][x]) for x in range(
            len(projects[project_id]['attribute9_files']))]

        if is_admin:
            filtered_projects = [x for x in projects.values() if x['accepted']]
        #  elif is_expert:
        else:
            filtered_projects = [x for x in projects.values(
            ) if x['accepted'] and x['email'] == current_user.email]
        return render_template('score.html',
                               form=form,
                               info='Scores successfully updated!',
                               projects=filtered_projects,
                               files=None if project_id is None else fix_files_list_images_top(
                                   projects[project_id]['project_files']),
                               files_constraints=None if project_id is None else fix_files_list_images_top(
                                   projects[project_id]['cm_restriction6_files']),
                               files_attributes_quality=None if project_id is None else fix_files_list_images_top(
                                   projects[project_id]['attribute9_files']),
                               project_id=project_id)
    if is_admin:
        filtered_projects = [x for x in projects.values() if x['accepted']]
    #  elif is_expert:
    else:
        filtered_projects = [x for x in projects.values(
        ) if x['accepted'] and x['email'] == current_user.email]
    return render_template('score.html',
                           form=form, info=None,
                           projects=filtered_projects,
                           files=None if project_id is None else fix_files_list_images_top(
                               projects[project_id]['project_files']),
                           files_constraints=None if project_id is None else fix_files_list_images_top(
                               projects[project_id]['cm_restriction6_files']),
                           files_attributes_quality=None if project_id is None else fix_files_list_images_top(
                               projects[project_id]['attribute9_files']),
                           project_id=project_id)


@app.route('/decision-support-system/recommendation', methods=['GET', 'POST'])
def recommend():
    form = RecommendForm()
    load_projects()

    if request.method == 'POST' and form.validate_on_submit():
        project = {
            'cm_restrictions': [form.cm_restriction1.data,
                                form.cm_restriction2.data,
                                form.cm_restriction3.data,
                                form.cm_restriction4.data,
                                form.cm_restriction5.data,
                                form.cm_restriction6.data,
                                form.cm_restriction7.data,
                                form.cm_restriction8.data,
                                form.cm_restriction9.data,
                                form.country.data,
                                form.city.data,
                                form.local_authority.data,
                                ]
        }
        # soft_num, soft_score = max_score(software_choice2(project['cm_restrictions'],
        #                                                   [(x['cm_restrictions'], x['application']) for x in projects.values() if x['history']]))

        # prjs = [x for x in projects.values() if x['history'] and compare_list(x['cm_restrictions']+[x['country'],x['city']),x['local_authority']],project['cm_restrictions'])>= 6]
        prjs = [x for x in projects.values() if x['history'] and compare_list(x['cm_restrictions']+[x['country'],x['city'],x['local_authority']], project['cm_restrictions'])>= 6]
        print(len(prjs))
        for prj in prjs:
            prj['aggregate_score'] = sum(prj['attribute_ratings'])
        return render_template('recommend.html',
                               form=form,
                               info='Scores successfully updated!',
                               projects=None if len(prjs) == 0 else prjs,
                               project=project,
                               software_names=software_names)
    return render_template('recommend.html',
                           form=form, info=None,
                           projects=[],
                           project=None,
                           software_names=software_names)


@app.route('/decision-support-system/manage-projects/<int:project_id>', methods=['GET', 'POST'])
@roles_required('Admin')
def accept(project_id):
    if project_id == 0:
        project_id = None
    if project_id is not None:
        project_id = str(project_id)
    form = ScoreForm()

    try:
        is_history = projects[project_id]['history']
    except (TypeError, KeyError):
        is_history = False

    if is_history:
        form.cm_restriction1.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction2.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction3.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction4.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction5.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction6.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction7.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction8.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction9.render_kw = {'readonly': True, 'disabled': True}
        form.attribute1.render_kw = {'readonly': True, 'disabled': True}
        form.attribute2.render_kw = {'readonly': True, 'disabled': True}
        form.attribute3.render_kw = {'readonly': True, 'disabled': True}
        form.attribute4.render_kw = {'readonly': True, 'disabled': True}
        form.attribute5.render_kw = {'readonly': True, 'disabled': True}
        form.attribute6.render_kw = {'readonly': True, 'disabled': True}
        form.attribute7.render_kw = {'readonly': True, 'disabled': True}
        form.attribute8.render_kw = {'readonly': True, 'disabled': True}
        form.attribute9.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction1.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction2.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction3.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction4.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction5.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction6.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction7.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction8.render_kw = {'readonly': True, 'disabled': True}
        form.cm_restriction9.render_kw = {'readonly': True, 'disabled': True}
        form.attribute1.render_kw = {'readonly': True, 'disabled': True}
        form.attribute2.render_kw = {'readonly': True, 'disabled': True}
        form.attribute3.render_kw = {'readonly': True, 'disabled': True}
        form.attribute4.render_kw = {'readonly': True, 'disabled': True}
        form.attribute5.render_kw = {'readonly': True, 'disabled': True}
        form.attribute6.render_kw = {'readonly': True, 'disabled': True}
        form.attribute7.render_kw = {'readonly': True, 'disabled': True}
        form.attribute8.render_kw = {'readonly': True, 'disabled': True}
        form.attribute9.render_kw = {'readonly': True, 'disabled': True}
    load_projects()
    if request.method == 'GET':
        if project_id is not None:
            form.title.data = projects[project_id]['title']
            form.organisation_url.data = projects[project_id]['organisation_url']
            form.country.data = projects[project_id]['country']
            form.city.data = projects[project_id]['city']
            form.local_authority.data = projects[project_id]['local_authority']
            form.involvement.data = projects[project_id]['involvement']
            form.date_of_project.data = datetime.datetime.strptime(
                projects[project_id]['date_of_project'], "%Y-%m-%d").date()
            form.application.data = projects[project_id]['application']
            form.version.data = projects[project_id]['version']
            try:
                form.award.data = projects[project_id]['awards']
            except:
                form.award.data = ""
            form.email.data = projects[project_id]['email']
            form.cm_restriction1.data = projects[project_id]['cm_restrictions'][0]
            form.cm_restriction2.data = projects[project_id]['cm_restrictions'][1]
            form.cm_restriction3.data = projects[project_id]['cm_restrictions'][2]
            form.cm_restriction4.data = projects[project_id]['cm_restrictions'][3]
            form.cm_restriction5.data = projects[project_id]['cm_restrictions'][4]
            form.cm_restriction6.data = projects[project_id]['cm_restrictions'][5]
            form.cm_restriction7.data = projects[project_id]['cm_restrictions'][6]
            form.cm_restriction8.data = projects[project_id]['cm_restrictions'][7]
            form.cm_restriction9.data = projects[project_id]['cm_restrictions'][8]
            form.attribute1.data = projects[project_id]['attribute_ratings'][0]
            form.attribute2.data = projects[project_id]['attribute_ratings'][1]
            form.attribute3.data = projects[project_id]['attribute_ratings'][2]
            form.attribute4.data = projects[project_id]['attribute_ratings'][3]
            form.attribute5.data = projects[project_id]['attribute_ratings'][4]
            form.attribute6.data = projects[project_id]['attribute_ratings'][5]
            form.attribute7.data = projects[project_id]['attribute_ratings'][6]
            form.attribute8.data = projects[project_id]['attribute_ratings'][7]
            form.attribute9.data = projects[project_id]['attribute_ratings'][8]
            #  Preparing delete files list

            try:
                form.project_before_files.choices = [(x, projects[project_id]['project_files'][x]) for x in range(
                    len(projects[project_id]['project_files']))]
            except  KeyError:
                projects[project_id]['project_files'] = []

            try:
                form.cm_restriction6_before_files.choices = [(x, projects[project_id]['cm_restriction6_files'][x]) for x in range(
                    len(projects[project_id]['cm_restriction6_files']))]
            except  KeyError:
                projects[project_id]['cm_restriction6_files'] = []

            try:
                form.attribute9_before_files.choices = [(x, projects[project_id]['attribute9_files'][x]) for x in range(
                    len(projects[project_id]['attribute9_files']))]
            except  KeyError:
                projects[project_id]['attribute9_files'] = []

    if request.method == 'POST' and form.validate_on_submit():
        projects[project_id].update({
            'cm_restrictions': [form.cm_restriction1.data,
                                form.cm_restriction2.data,
                                form.cm_restriction3.data,
                                form.cm_restriction4.data,
                                form.cm_restriction5.data,
                                form.cm_restriction6.data,
                                form.cm_restriction7.data,
                                form.cm_restriction8.data,
                                form.cm_restriction9.data],
            'attribute_ratings': [form.attribute1.data,
                                  form.attribute2.data,
                                  form.attribute3.data,
                                  form.attribute4.data,
                                  form.attribute5.data,
                                  form.attribute6.data,
                                  form.attribute7.data,
                                  form.attribute8.data,
                                  form.attribute9.data]
        })

        # project  files
        for ind in form.project_before_files.data[::-1]:
            os.remove(base_dir + '/static/upload/file/' +
                      projects[project_id]['project_files'][ind])
            del projects[project_id]['project_files'][ind]

        project_filenames = []

        for item in request.files.getlist('project_files'):
            if item:
                project_filenames.append(files.save(item))

        try:
            projects[project_id]['project_files'] += project_filenames
        except KeyError:
            projects[project_id]['project_files'] = project_filenames


        # project constraints  files
        for ind in form.cm_restriction6_before_files.data[::-1]:
            os.remove(base_dir + '/static/upload/file/' +
                      projects[project_id]['cm_restriction6_files'][ind])
            del projects[project_id]['cm_restriction6_files'][ind]

        cm_restriction6_files = []

        for item in request.files.getlist('cm_restriction6_files'):
            if item:
                cm_restriction6_files.append(files.save(item))

        try:
            projects[project_id]['cm_restriction6_files'] += cm_restriction6_files
        except KeyError:
            projects[project_id]['cm_restriction6_files'] = cm_restriction6_files


        # project Attributes (Section 2) COST Files
        for ind in form.attribute9_before_files .data[::-1]:
            os.remove(base_dir + '/static/upload/file/' +
                      projects[project_id]['attribute9_files'][ind])
            del projects[project_id]['attribute9_files'][ind]

        attribute9_files = []

        for item in request.files.getlist('attribute9_files'):
            if item:
                attribute9_files.append(files.save(item))

        try:
            projects[project_id]['attribute9_files'] += attribute9_files
        except KeyError:
            projects[project_id]['attribute9_files'] = attribute9_files


        # End Project files


        projects[project_id]['accepted'] = True

        save_projects()
        form.project_before_files.choices = [(x, projects[project_id]['project_files'][x]) for x in range(
            len(projects[project_id]['project_files']))]
        form.cm_restriction6_before_files.choices = [(x, projects[project_id]['cm_restriction6_files'][x]) for x in range(
            len(projects[project_id]['cm_restriction6_files']))]

        form.attribute9_before_files.choices = [(x, projects[project_id]['attribute9_files'][x]) for x in range(
            len(projects[project_id]['attribute9_files']))]

        return render_template('accept.html',
                               form=form,
                               info='Project data successfully updated!',
                               projects=list(projects.values()),
                               project_id=project_id,
                               files=None if project_id is None else fix_files_list_images_top(
                                   projects[project_id]['project_files']),
                               files_constraints=None if project_id is None else fix_files_list_images_top(
                                   projects[project_id]['cm_restriction6_files']),
                               files_attributes_quality=None if project_id is None else fix_files_list_images_top(
                                   projects[project_id]['attribute9_files']),
                               accepted=True if project_id is None else projects[project_id]['accepted'],
                               history=True if project_id is None else projects[project_id]['history'])
    if request.method == "POST" and not form.validate_on_submit():
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                print(err)
    return render_template('accept.html',
                           form=form, info=None,
                           projects=list(projects.values()),
                           project_id=project_id,
                           files=None if project_id is None else fix_files_list_images_top(
                               projects[project_id]['project_files']),
                           files_constraints=None if project_id is None else fix_files_list_images_top(
                               projects[project_id]['cm_restriction6_files']),
                           files_attributes_quality=None if project_id is None else fix_files_list_images_top(
                               projects[project_id]['attribute9_files']),
                           accepted=True if project_id is None else projects[project_id]['accepted'],
                           history=True if project_id is None else projects[project_id]['history'])


@app.route('/decision-support-system/manage-projects/accept/<int:project_id>')
@roles_required('Admin')
def accept_project(project_id):
    load_projects()
    project_id = str(project_id)
    projects[project_id]['accepted'] = True
    save_projects()
    return redirect(url_for('accept', project_id=0))


@app.route('/decision-support-system/manage-projects/add-history/<int:project_id>')
@roles_required('Admin')
def add_history_project(project_id):
    load_projects()
    project_id = str(project_id)
    projects[project_id]['history'] = True
    save_projects()
    return redirect(url_for('accept', project_id=0))


@app.route('/decision-support-system/manage-projects/remove-history/<int:project_id>')
@roles_required('Admin')
def remove_history_project(project_id):
    load_projects()
    project_id = str(project_id)
    projects[project_id]['history'] = False
    save_projects()
    return redirect(url_for('accept', project_id=0))


@app.route('/decision-support-system/manage-projects/del/<int:project_id>')
@roles_required('Admin')
def delete_project(project_id):
    load_projects()
    project_id = str(project_id)
    del projects[project_id]
    save_projects()
    return redirect(url_for('accept', project_id=0))


@app.route('/decision-support-system/manage-users/<int:user_id>', methods=['GET', 'POST'])
@roles_required('Admin')
def useradmin(user_id):
    if user_id == 0:
        user_id = None
    form = UserAdminForm()

    users = User.query.all()
    roles = Role.query.all()

    if request.method == 'GET':
        if user_id is not None and len([x for x in users if x.id == user_id]) > 0:
            user = [x for x in users if x.id == user_id][0]
            form.email.data = user.email
            form.first_name.data = user.first_name
            form.last_name.data = user.last_name
            form.roles.choices = [(x.id, x.name) for x in roles]
            form.roles.data = [x.id for x in user.roles]
    if request.method == 'POST' and form.validate_on_submit():
        user = [x for x in users if x.id == user_id][0]
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.email_confirmed_at = datetime.datetime.utcnow()
        user.roles = [x for x in roles if x.id in form.roles.data]
        db.session.commit()

        form.roles.choices = [(x.id, x.name) for x in roles]
        form.roles.data = [x.id for x in user.roles]
        if request.form['submit_update_user'] == "Update and send email":
            send_email_to_new_user(form.email.data)

        return render_template('useradmin.html',
                               form=form,
                               info='Scores successfully updated!',
                               users=users,
                               user_id=user_id)
    return render_template('useradmin.html',
                           form=form, info=None,
                           users=users,
                           user_id=user_id)


@app.route('/decision-support-system/manage-users/add', methods=['POST'])
@roles_required('Admin')
def add_user():
    form = UserAdminForm()
    if request.method == 'POST' and form.validate_on_submit():
        users = User.query.all()
        if len([x for x in users if x.email == form.email.data]) == 0:
            roles = Role.query.all()
            user = User(
                email=form.email.data,
                email_confirmed_at=datetime.datetime.utcnow(),
                password=user_manager.hash_password('123456'),
                first_name=form.first_name.data,
                last_name=form.last_name.data
            )
            for role in [x for x in roles if x.id in form.roles.data]:
                user.roles.append(role)
            db.session.add(user)
            db.session.commit()

    return redirect(url_for('useradmin', user_id=0))


@app.route('/decision-support-system/manage-users/del/<int:user_id>')
@roles_required('Admin')
def delete_user(user_id):
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('useradmin', user_id=0))


@app.route('/list-of-4d-bim-professional-dss-users/professionals-offering-a-4d-bim-recommendation')
def projects():
    load_projects()
    return render_template('projects.html',
                           projects=[x for x in projects.values() if x['scored']],)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html')


nav = Nav()


@nav.navigation()
def mynavbar():
    items = [View(app_name, 'index'),
             Subgroup('Website Design',
                      View('Introduction', 'introduction'),
                      View('Design', 'instruction')),
             Subgroup('Construction Management',
                      View('4D BIM Added Value', 'management'),
                      View('Risk Mitigation', 'risk_mitigation'),
                      View('Exemplar Aspects of Evaluation', 'exemplar_aspect')),
             Subgroup('Best Practice 4D BIM',
                      View('Best Practice Evaluation', 'bim_tool'),
                      View('Explained', 'explained'),
                      View('Project Constraints', 'constraints'),
                      View('4D BIM Attributes', 'attributes'),
                      View('Planned Outputs', 'planned_output'))]
    # items = [View(app_name, 'index'),
    #          View('Recommendation', 'recommend')]
    if current_user.is_authenticated:
        is_expert = len(
            [role for role in current_user.roles if role.name == 'Expert']) > 0
        is_admin = len(
            [role for role in current_user.roles if role.name == 'Admin']) > 0
        if is_expert and is_admin:
            items.append(Subgroup('Decision Support System',
                                  View('Recommendation', 'recommend'),
                                  View('4D BIM Expert - Add Project Details', 'add'),
                                  View('Score Projects', 'score', project_id=0),
                                  View('Manage Projects',
                                       'accept', project_id=0),
                                  View('Manage Users', 'useradmin', user_id=0)))
        elif is_expert:
            items.append(Subgroup('Decision Support System',
                                  View('Recommendation', 'recommend'),
                                  View('4D BIM Expert - Add Project Details', 'add'),
                                  View('Score Projects', 'score', project_id=0)))
        elif is_admin:
            items.append(Subgroup('Decision Support System',
                                  View('Recommendation', 'recommend'),
                                  View('4D BIM Expert - Add Project Details', 'add'),
                                  View('Manage Projects',
                                       'accept', project_id=0),
                                  View('Manage Users', 'useradmin', user_id=0)))
        name = current_user.first_name + ' ' + current_user.last_name
        if name == ' ':
            name = 'User'
        items.append(Subgroup(name,
                              View('Edit Profile', 'user.edit_user_profile'),
                              View('Log out', 'user.logout')))
    else:
        items.append(Subgroup('Decision Support System',
                              View('Project Based Recommendation Required',
                                   'recommend'),
                              View('4D BIM Expert - Add Project Details', 'add')))
        items.append(Subgroup('Log in',
                              View('Log in', 'user.login')))

    items.append((Subgroup('Professional DSS Users',
                           View('Professional Recommendations', 'projects'))))

    return Navbar(*items)


nav.init_app(app)


@nav.renderer()
class InvertedRenderer(BootstrapRenderer):
    def visit_Navbar(self, node):
        root = super(InvertedRenderer, self).visit_Navbar(node)
        root['class'] = 'navbar navbar-inverse'
        return root


register_renderer(app, 'inverted', InvertedRenderer)

Bootstrap(app)


def send_email(receiver_email, project):
    port = 587  # For SSL
    smtp_server = "smtp.office365.com"
    sender_email = "dbimdecisions-no-reply@outlook.com"  # Enter your address
    password = "Azerty123456789"

    message = """Project Title & Organisation: %s
                Organisation URL: %s
                Country: %s
                City: %s
                Local Authority: %s
                Individual Project Involvement: %s
                Date of Project Completion: %s
                4D Software Application Used: %s
                Software Application Version: %s
                E-mail: %s"""

    server = smtplib.SMTP(smtp_server, port)
    server.ehlo()
    server.starttls()
    server.login(sender_email, password)

    msg = MIMEText(message % (project['title'],
                              project['organisation_url'],
                              project['country'],
                              project['city'],
                              project['local_authority'],
                              project['involvement'],
                              project['date_of_project'],
                              software_names[project['application']],
                              project['version'],
                              project['email']))
    msg['Subject'] = "New 4D BIM Project"
    msg['From'] = "4dbimdecisions.com"
    msg['To'] = receiver_email

    server.sendmail(sender_email, receiver_email, msg.as_string())
    server.quit()


def send_email_to_new_user(receiver_email):
    port = 587  # For SSL
    smtp_server = "smtp.office365.com"
    sender_email = "dbimdecisions-no-reply@outlook.com"  # Enter your address
    password = "Azerty123456789"

    message = """Hello,
                Your account was created. You can login in https://4dbimdecisions.com/user/sign-in:
                Your login: %s
                Your password: 123456 """

    server = smtplib.SMTP(smtp_server, port)
    server.ehlo()
    server.starttls()
    server.login(sender_email, password)

    msg = MIMEText(message % (receiver_email))

    msg['Subject'] = "New 4D BIM Project"
    msg['From'] = "4dbimdecisions.com"
    msg['To'] = receiver_email

    server.sendmail(sender_email, receiver_email, msg.as_string())
    server.quit()


def fix_files_list_images_top(list):
    # images_list =  [ item for item in list if (item.endswith(".png") or item.endswith(".jpg") or item.endswith(".jpeg") or item.endswith(".gif"))]
    images_list = []
    for i in range(len(list)):
        print(list[i])
        if list[i].endswith(".png") or list[i].endswith(".jpg") or list[i].endswith(".jpeg") or list[i].endswith(".gif"):
            item_0 = list.pop(i)
            list.insert(0,item_0)
    return list


if __name__ == '__main__':
    app.run(debug=True)
