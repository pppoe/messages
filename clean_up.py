import glob, json
for fpath in glob.glob('messages/*.json'):
    data = json.load(open(fpath))
    if len(data['image']) > 0 and data['image'].startswith('https://media.mas.to/masto-public/'):
        data['image'] = data['image'].replace('masto-public/', '').replace('/small', '/original')
        json.dump(data, open(fpath, 'w'))

