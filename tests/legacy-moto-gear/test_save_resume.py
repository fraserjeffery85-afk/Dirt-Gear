"""Saved designs survive a fresh document load and preserve editable artwork."""
import io
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'outputs/Moto-Gear/source'))
import app
from PIL import Image

template = Path(__file__).resolve().parent/'test-template.psd'
assert template.is_file()
with tempfile.TemporaryDirectory() as tmp:
    os.environ['LOCALAPPDATA'] = tmp
    doc = app.Document(template, 'Test gear.psd')
    art = Image.new('RGBA', (16, 16), (200, 20, 30, 255))
    doc.assets['logo'] = {'name':'My logo', 'image':art}
    doc.state['name'] = 'My saved gear'
    doc.state['artworks'] = [{'id':'placed-logo','asset':'logo','name':'My logo',
        'x':64,'y':64,'width':16,'height':16,'rotation':0,'opacity':1,'visible':True}]
    app.DOC = doc
    client = app.app.test_client()
    headers = {'X-Moto-Token':app.TOKEN}
    saved = client.post('/api/project/quick-save', json=doc.state, headers=headers)
    assert saved.status_code == 200, saved.json
    path = Path(saved.json['saved'])
    assert path.is_file() and path.parent == app.project_library()
    recent = client.get('/api/project/recent', headers=headers).json['projects']
    assert recent[0]['name'] == 'My saved gear'
    app.DOC = None
    reopened = client.post('/api/project/reopen', json={'id':recent[0]['id']}, headers=headers)
    assert reopened.status_code == 200, reopened.json
    assert app.DOC.state == doc.state
    assert app.DOC.assets['logo']['image'].tobytes() == art.tobytes()
    assert app.DOC.quick_save_path == path
    exported = client.post('/api/export/pnt', json=app.DOC.state, headers=headers)
    assert exported.status_code == 200 and set(app.read_pnt(exported.data)) == {'rider','rider_n','rider_r'}
    class SaveDialog:
        def create_file_dialog(self, *args, **kwargs):
            return str(Path(tmp)/'renamed paint.pnt')
    app.NATIVE_WINDOW = SaveDialog()
    with app.app.test_request_context(headers={'X-Moto-Desktop':'1'}):
        result = app.download(exported.data, 'original name.pnt')
    app.NATIVE_WINDOW = None
    assert result.json['filename'] == 'renamed paint.pnt'
    renamed = (Path(tmp)/'renamed paint.pnt').read_bytes()
    assert renamed[4:104].split(b'\0')[0] == b'renamed paint'
    assert set(app.read_pnt(renamed)) == {'rider','rider_n','rider_r'}
    blocked = client.post('/api/project/reopen', json={'id':'../outside.motogear'}, headers=headers)
    assert blocked.status_code == 400

print('Save for later, reopen, editable artwork, and paint packing passed')
