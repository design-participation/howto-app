import uuid
import os

from aiohttp import web
from aiohttp_session import get_session, new_session
import aiohttp_jinja2

from util import routes, login_required, run_command, remove_file, get_user
from backend import users, history
import thumbnail

async def upload_picture(field):
    # TODO: should check content for actual picture; should also limit size on the client side
    extension = field.filename.split('.')[-1].lower()
    if extension not in ['jpg', 'jpeg', 'png', 'gif']:
        raise web.HTTPBadRequest(reason='Picture file type not allowed, please use jpg, jpeg, png or gif')
    base = str(uuid.uuid4())
    orig_filename = 'orig-%s.%s' % (base, extension)
    filename = '%s.jpg' % base
    size = 0
    with open('./data/pictures/' + orig_filename, 'wb') as f:
        while True:
            chunk = await field.read_chunk()  # 8192 bytes by default.
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)
            if size > 1024 * 1024 * 10: # max 10M 
                fp.close()
                os.unlink('./data/pictures/' + orig_filename)
                raise web.HTTPBadRequest(reason='Picture file too large')
    #status, stdout, stderr = await run_command('./src/make-thumbnail.sh "./data/pictures/%s" "./data/pictures/%s"' % (orig_filename, filename))
    if not thumbnail.make_thumbnail('./data/pictures/' + orig_filename, './data/pictures/' + filename, 512):
        remove_file('./data/pictures/' + filename)
        #raise web.HTTPBadRequest(reason='Cannot resize picture (status=%d, stdout="%s", stderr="%s")' % (status, stdout, stderr))
        raise web.HTTPBadRequest(reason='Cannot resize picture')
    remove_file('./data/pictures/' + orig_filename)
    return '/pictures/' + filename

#GET /user => new user form
@routes.get('/new-user')
@aiohttp_jinja2.template('new_user.html')
async def new_user_form(request):
    return {}

#POST /new-user (email, password) => create user
@routes.post('/new-user')
@aiohttp_jinja2.template('new_user.html')
async def new_user(request):
    reader = await request.multipart()
    data = {}

    while True: # handle file upload and other fields
        field = await reader.next()
        if not field:
            break
        if field.name in ['email', 'name', 'password']:
            data[field.name] = (await field.read(decode=True)).decode('utf8')
        elif field.name == 'picture':
            if field.filename == '': # skip if no file was provided
                continue
            data['picture'] = await upload_picture(field)
        else:
            raise web.HTTPBadRequest()

    email = data.get('email', '')
    password = data.get('password', '')
    name = data.get('name', '')
    picture = data.get('picture', '')

    if picture.strip() == '':
        picture = 'https://api.adorable.io/avatars/512/' + email
    error = None
    if 'email' == '' or password == '':
        error = 'invalid request'
    user_id = await users.add(password=password, email=email, name=name, picture=picture)
    if user_id is None:
        error = 'email already exists'
    if error is not None:
        remove_file('./data/' + picture)
        return {'email': email, 'name': name, 'error_message': error}
    else:
        session = await new_session(request)
        session['user_id'] = str(user_id)
        await history.add(user_id, 'created')
        raise web.HTTPFound('/')

#GET /login => login form
@routes.get('/login')
@aiohttp_jinja2.template('login.html')
async def login_form(request):
    import sys
    if '-debug' in sys.argv:
        result = []
        for user in await users.list():
            user['href'] = '/debug:login/' + str(user['_id'])
            result.append(user)
        import random
        random.shuffle(result)
        return {'users': result}
    return {}

#GET /user => show form to channge profile information
@routes.get('/user-modify')
@login_required
@aiohttp_jinja2.template('user-modify.html')
async def logout(request):
    return {}

#GET /user => show user profile
@routes.get('/user')
@login_required
@aiohttp_jinja2.template('user.html')
async def logout(request):
    return {}

#POST /user/change-picture => change picture
@routes.post('/user/change-picture')
@login_required
@aiohttp_jinja2.template('user.html')
async def change_picture(request):
    reader = await request.multipart()
    picture = None
    field = await reader.next()
    if field and field.name == 'picture' and field.filename.strip() != '':
        picture = await upload_picture(field)
    else:
        raise web.HTTPBadRequest()
    print('picture', picture)
    user = await get_user(request)
    await users.change_picture(user['_id'], picture)
    user['picture'] = picture
    await history.add(user['_id'], 'changed-picture', {'picture': picture})
    raise web.HTTPFound('/user')
    #return {'info_message': 'Picture changed'}

#POST /user/change-password => change password
@routes.post('/user/change-password')
@login_required
@aiohttp_jinja2.template('user.html')
async def change_password(request):
    data = await request.post()
    user = await get_user(request)
    old_password = data.get('old_password', None)
    new_password = data.get('new_password', None)
    if user is None or old_password is None or new_password is None:
        raise web.HTTPBadRequest(reason='missing password')
    if not await users.change_password(user['_id'], old_password, new_password):
        raise web.HTTPBadRequest(reason='wrong password')
    await history.add(user['_id'], 'changed-password')
    raise web.HTTPFound('/user')
    #return {'info_message': 'Password changed'}

#GET /logout => remove user_id from session
@routes.get('/logout')
@login_required
async def logout(request):
    session = await get_session(request)
    if 'user_id' in session:
        user = await get_user(request)
        await history.add(user['_id'], 'logout')
        del session['user_id']
    raise web.HTTPFound('/login')

#POST /login (email, password) => login as existing user
@routes.post('/login')
@aiohttp_jinja2.template('login.html')
async def login(request):
    data = await request.post()
    email = data.get('email', '')
    password = data.get('password', '')
    user_id = await users.login(email, password)
    if user_id is not None:
        session = await new_session(request)
        session['user_id'] = str(user_id)
        await history.add(user_id, 'login')
        raise web.HTTPFound('/')
    else:
        return {'email': email, 'error_message': 'invalid credentials'}

