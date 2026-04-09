import urllib.request
import json
import os
import time

os.makedirs('server/data_ingestion/logs', exist_ok=True)

url = 'https://nodocchi.moe/api/listuser.php?name=ASAPIN'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    resp = urllib.request.urlopen(req).read().decode('utf-8')
    data = json.loads(resp)
    
    if 'list' in data:
        games = data['list']
    else: games = data
    
    downloaded = 0
    # Let's filter Houou table only (-00a9- or -0089-)
    # Actually, ASASPIN plays Houou a lot, let's just get whatever games, 
    # but preferably Houou if we check log_id
    
    for g in games:
        if downloaded >= 100:
            break
            
        full_url = g.get('url', '')
        if 'log=' not in full_url:
            continue
            
        log_id = full_url.split('log=')[1]
        
        # We only really want standard games if possible (not sanma)
        if g.get('playernum') != 4:
            continue
            
        mjlog_url = f'https://tenhou.net/0/log/?{log_id}'
        try:
            req_log = urllib.request.Request(mjlog_url, headers={'User-Agent': 'Mozilla/5.0'})
            log_data = urllib.request.urlopen(req_log).read()
            # Some old logs might not be accessible from tenhou anymore, check if xml or error
            if len(log_data) < 100 or b'error' in log_data.lower():
                continue
                
            with open(f'server/data_ingestion/logs/{log_id}.mjlog', 'wb') as f:
                f.write(log_data)
            downloaded += 1
            if downloaded % 10 == 0:
                print(f'[{downloaded}/100] Downloaded {log_id}.mjlog')
        except Exception as e:
            # print(f'Failed {log_id}: {e}')
            pass
        time.sleep(0.5)
        
    print(f'Done downloading {downloaded} logs.')
except Exception as e:
    print('Failed API:', e)
