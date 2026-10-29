"""Exercise the MX Bikes install path without changing the user's game files."""
import io
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'outputs/Moto-Gear/source'))
import app
from PIL import Image
from packing import tga_bytes, read_pnt


class FakeDocument:
    def __init__(self):
        self.state = {'name': 'Test Moto Gear'}

    def update(self, state):
        self.state = state

    def textures(self):
        color = Image.new('RGB', (4, 4), (20, 40, 60))
        normal = Image.new('RGB', (4, 4), (128, 128, 255))
        black = Image.new('RGB', (4, 4), (0, 0, 0))
        return {'rider': tga_bytes(color), 'rider_n': tga_bytes(normal, True),
                'rider_r': tga_bytes(black, True)}


with tempfile.TemporaryDirectory() as tmp:
    folder = Path(tmp)/'default_mx/paints'
    folder.mkdir(parents=True)
    app.rider_paint_folders = lambda: {'default_mx': folder}
    app.DOC = FakeDocument()
    client = app.app.test_client()
    headers = {'X-Moto-Token': app.TOKEN}
    assert client.get('/api/game/paint-folders', headers=headers).json['models'] == ['default_mx']
    request = {'model': 'default_mx', 'state': {'name': 'Test Moto Gear'}}
    response = client.post('/api/game/install-pnt', json=request, headers=headers)
    assert response.status_code == 200, response.json
    output = folder/'Test Moto Gear.pnt'
    assert response.json['filename'] == output.name and output.exists()
    assert set(read_pnt(output.read_bytes())) == {'rider', 'rider_n', 'rider_r'}
    assert client.post('/api/game/install-pnt', json=request, headers=headers).json['exists']
    request['replace'] = True
    assert client.post('/api/game/install-pnt', json=request, headers=headers).json['saved'] == str(output)
    request['model'] = '../other'
    assert client.post('/api/game/install-pnt', json=request, headers=headers).status_code == 400

print('MX Bikes folder listing and PNT installation passed')
