"""Run a synthetic trial from availability through staff review, entirely offline."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from .store import Store


def main():
    now=[int(datetime.now(timezone.utc).timestamp())]
    scratch=Path.cwd()/'work/trial-demo'
    scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        s=Store(Path(tmp)/'demo.sqlite3',clock=lambda:now[0])
        s.pause(False,900)
        start=((now[0]+2*86400+899)//900)*900
        windows=[[start,start+3*3600]]
        s.approve(100,'normal',2,900)
        s.availability(100,windows,'UTC',True)
        t=s.create(200,300,'normal',60,14,900)
        s.applicant_availability(t['id'],200,windows,'UTC')
        t=s.get(t['id'])
        print(f"Trial #{t['id']}: availability collected")
        slots=s.available_slots(t['id'],100)
        print(f'Matched {len(slots)} possible start times with an opted-in volunteer')
        t=s.propose(t['id'],100,slots[0][0],t['revision'])
        print(f"Volunteer proposed a time: {t['status']}")
        t=s.confirm(t['id'],200,t['revision'])
        print(f"Applicant confirmed: {t['status']}")
        now[0]=t['end']
        s.feedback(t['id'],100,'recommend','Synthetic demo: listened and participated.')
        print(f"Private feedback recorded: {s.get(t['id'])['status']}")
        s.close(t['id'],900,'accepted')
        print('Staff recorded the outcome; no membership roles changed')
        print('Offline demo complete. No Discord connection or messages.')


if __name__=='__main__':
    main()
