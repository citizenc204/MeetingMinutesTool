from __future__ import annotations
import re, uuid, shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List
from lxml import etree
from models import Project, Track, Meeting, MeetingHeader, Section, Item, Note

def slugify(name: str) -> str:
    s = name.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]+", "-", s).strip("-")
    return s or f"obj-{uuid.uuid4().hex[:6]}"

def _today() -> str:
    return date.today().isoformat()

def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    from calendar import monthrange
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day)

class XMLStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        (self.root / "Projects").mkdir(parents=True, exist_ok=True)
        (self.root / "logs").mkdir(parents=True, exist_ok=True)

    # Paths
    def proj_path(self, p: Project) -> Path: return self.root / "Projects" / p.slug
    def proj_xml(self, p: Project) -> Path: return self.proj_path(p) / "project.xml"
    def track_path(self, proj: Project, t: Track) -> Path: return self.proj_path(proj) / "Tracks" / t.slug
    def track_xml(self, proj: Project, t: Track) -> Path: return self.track_path(proj, t) / "track.xml"
    def meetings_dir(self, proj: Project, t: Track) -> Path:
        p = self.track_path(proj, t) / "Meetings"; p.mkdir(parents=True, exist_ok=True); return p
    def meeting_dir(self, proj: Project, t: Track, number: str) -> Path:
        p = self.meetings_dir(proj, t) / number; p.mkdir(parents=True, exist_ok=True)
        (p/"attachments").mkdir(parents=True, exist_ok=True); (p/"exports").mkdir(parents=True, exist_ok=True); return p
    def meeting_xml(self, proj: Project, t: Track, number: str) -> Path:
        return self.meeting_dir(proj, t, number) / "meeting.xml"

    # Project CRUD
    def save_project(self, p: Project) -> None:
        r = etree.Element("Project", id=p.id); etree.SubElement(r, "Name").text = p.name
        self.proj_path(p).mkdir(parents=True, exist_ok=True)
        etree.ElementTree(r).write(str(self.proj_xml(p)), pretty_print=True, xml_declaration=True, encoding="utf-8")

    def create_project(self, name: str) -> Project:
        p = Project(id=uuid.uuid4().hex, name=name, slug=slugify(name), tracks=[]); self.save_project(p); return p

    def delete_project(self, project_slug: str) -> None:
        pdir = self.root / "Projects" / project_slug
        if pdir.exists(): shutil.rmtree(pdir)

    # Track CRUD
    def save_track(self, proj: Project, t: Track) -> None:
        root = etree.Element("Track", id=t.id)
        etree.SubElement(root, "Name").text = t.name
        defs = etree.SubElement(root, "Defaults")
        etree.SubElement(defs, "Location").text = t.defaults_location
        etree.SubElement(defs, "TeamsLink").text = t.defaults_teams_link
        etree.SubElement(defs, "Recurrence", mode=t.recurrence_mode, interval=str(t.recurrence_interval))
        sects = etree.SubElement(root, "SectionTemplates")
        for s in t.section_templates: etree.SubElement(sects, "Section", name=s)
        self.track_path(proj, t).mkdir(parents=True, exist_ok=True)
        etree.ElementTree(root).write(str(self.track_xml(proj, t)), pretty_print=True, xml_declaration=True, encoding="utf-8")

    def create_track(self, proj: Project, name: str) -> Track:
        t = Track(id=uuid.uuid4().hex, name=name, slug=slugify(name)); self.save_track(proj, t); return t

    def delete_track(self, project_slug: str, track_slug: str) -> None:
        tdir = self.root / "Projects" / project_slug / "Tracks" / track_slug
        if tdir.exists(): shutil.rmtree(tdir)

    # Meeting CRUD
    def next_meeting_number(self, proj: Project, t: Track) -> str:
        md = self.meetings_dir(proj, t); maxn = 0
        for d in md.iterdir():
            if d.is_dir() and d.name.isdigit():
                try: maxn = max(maxn, int(d.name))
                except: pass
        return f"{maxn+1:04d}"

    def latest_meeting_number(self, proj: Project, t: Track):
        md = self.meetings_dir(proj, t); nums = []
        for d in md.iterdir():
            if d.is_dir() and d.name.isdigit(): nums.append(int(d.name))
        return f"{max(nums):04d}" if nums else None

    def create_meeting(self, proj: Project, t: Track, copy_from_number=None) -> Meeting:
        number = self.next_meeting_number(proj, t)
        if copy_from_number is None: copy_from_number = self.latest_meeting_number(proj, t)
        header = MeetingHeader(topic=f"{t.name}", date=_today(), start="09:00", end="10:00", location=t.defaults_location, teams_link=t.defaults_teams_link)
        m = Meeting(id=uuid.uuid4().hex, number=number, header=header, sections=[], items=[])
        if copy_from_number:
            prev = self.load_meeting(proj, t, copy_from_number)
            if prev:
                m.sections = [Section(id=s.id, name=s.name, order=s.order) for s in prev.sections]
                for it in prev.items:
                    if it.status in ("OPEN", "INFO"):
                        m.items.append(Item(id=uuid.uuid4().hex, description=it.description, status=it.status,
                                            assignee_id=it.assignee_id, priority=it.priority, due_date=it.due_date,
                                            tags=list(it.tags), order=it.order, section_name=it.section_name, notes=[]))
        self.save_meeting(proj, t, m); return m

    def create_next_meeting_respecting_recurrence(self, proj: Project, t: Track) -> Meeting:
        prev_num = self.latest_meeting_number(proj, t)
        m = self.create_meeting(proj, t, copy_from_number=prev_num)
        base_date = date.today()
        if prev_num:
            prev = self.load_meeting(proj, t, prev_num)
            if prev:
                try: y,mn,d = [int(x) for x in prev.header.date.split("-")]; base_date = date(y,mn,d)
                except: pass
        if t.recurrence_mode == "monthly":
            nd = _add_months(base_date, max(1, t.recurrence_interval))
        else:
            weeks = t.recurrence_interval if t.recurrence_mode == "weekly" else (t.recurrence_interval * 2 if t.recurrence_mode == "biweekly" else 1)
            nd = base_date + timedelta(days=7*weeks)
        m.header.date = nd.isoformat(); self.save_meeting(proj, t, m); return m

    def finalize_meeting(self, proj: Project, t: Track, number: str) -> None:
        m = self.load_meeting(proj, t, number)
        if not m: return
        m.finalized_at = datetime.now().isoformat(timespec="seconds"); self.save_meeting(proj, t, m)

    def delete_meeting(self, project_slug: str, track_slug: str, number: str) -> None:
        mdir = self.root / "Projects" / project_slug / "Tracks" / track_slug / "Meetings" / number
        if mdir.exists(): shutil.rmtree(mdir)

    # XML load/save
    def load_meeting(self, proj: Project, t: Track, number: str) -> Meeting | None:
        xmlp = self.meeting_xml(proj, t, number)
        if not xmlp.exists(): return None
        try:
            r = etree.parse(str(xmlp)).getroot()
        except Exception as e:
            (self.root / "logs" / "app.log").open("a", encoding="utf-8").write(f"[load_meeting] {xmlp}: {e}\n"); return None
        header = MeetingHeader(
            topic=r.findtext("Header/Topic") or "", date=r.findtext("Header/Date") or _today(),
            start=r.findtext("Header/Start") or "09:00", end=r.findtext("Header/End") or "10:00",
            location=r.findtext("Header/Location") or t.defaults_location, teams_link=r.findtext("Header/TeamsLink") or t.defaults_teams_link,
        )
        m = Meeting(id=r.get("id") or uuid.uuid4().hex, number=r.get("number") or "0001", header=header, sections=[], items=[])
        for se in r.findall("Agenda/Section"):
            s = Section(id=se.get("id") or uuid.uuid4().hex, name=se.get("name") or "", order=int(se.get("order") or 0))
            m.sections.append(s)
            for ie in se.findall("Item"):
                it = Item(
                    id=ie.get("id") or uuid.uuid4().hex, description=ie.findtext("Description") or "",
                    status=ie.get("status") or "OPEN",
                    assignee_id=(ie.find("Assignee").get("ref") if ie.find("Assignee") is not None else None),
                    priority=ie.findtext("Priority") or "Normal", due_date=ie.findtext("DueDate"),
                    tags=[te.text or "" for te in ie.findall("Tags/Tag")], order=int(ie.get("order") or 0),
                    section_name=s.name, notes=[]
                )
                for ne in ie.findall("Notes/Note"):
                    it.notes.append(Note(
                        id=ne.get("id") or uuid.uuid4().hex, text=ne.text or "",
                        meeting_date=ne.get("meetingDate") or m.header.date,
                        created_at=ne.get("createdAt") or datetime.now().isoformat(timespec="seconds"),
                        is_addendum=(ne.get("addendum") == "true")
                    ))
                m.items.append(it)
        fin = r.findtext("FinalizedAt"); m.finalized_at = fin if fin else None
        return m

    def save_meeting(self, proj: Project, t: Track, m: Meeting) -> None:
        root = etree.Element("Meeting", id=m.id, number=m.number)
        h = etree.SubElement(root, "Header")
        for tag, val in [("Topic", m.header.topic), ("Date", m.header.date), ("Start", m.header.start),
                         ("End", m.header.end), ("Location", m.header.location), ("TeamsLink", m.header.teams_link)]:
            etree.SubElement(h, tag).text = val
        agenda = etree.SubElement(root, "Agenda")
        for s in sorted(m.sections, key=lambda x: x.order):
            se = etree.SubElement(agenda, "Section", id=s.id, name=s.name, order=str(s.order))
            for it in sorted([i for i in m.items if i.section_name == s.name], key=lambda x: x.order):
                ie = etree.SubElement(se, "Item", id=it.id, status=it.status, order=str(it.order))
                etree.SubElement(ie, "Description").text = it.description
                if it.assignee_id: etree.SubElement(ie, "Assignee", ref=it.assignee_id)
                etree.SubElement(ie, "Priority").text = it.priority
                if it.due_date: etree.SubElement(ie, "DueDate").text = it.due_date
                tags = etree.SubElement(ie, "Tags")
                for tg in it.tags: etree.SubElement(tags, "Tag").text = tg
                notes = etree.SubElement(ie, "Notes")
                for n in it.notes:
                    ne = etree.SubElement(notes, "Note", id=n.id, meetingDate=n.meeting_date, createdAt=n.created_at, addendum=str(n.is_addendum).lower())
                    ne.text = n.text
        if m.finalized_at: etree.SubElement(root, "FinalizedAt").text = m.finalized_at
        mp = self.meeting_xml(proj, t, m.number); tmp = mp.with_suffix(".tmp")
        etree.ElementTree(root).write(str(tmp), pretty_print=True, xml_declaration=True, encoding="utf-8"); tmp.replace(mp)

    # Graph
    def load_projects(self) -> List[Project]:
        out: List[Project] = []
        root = self.root / "Projects"
        if not root.exists(): return out
        for d in root.iterdir():
            if not d.is_dir(): continue
            xmlp = d / "project.xml"
            if not xmlp.exists(): continue
            try:
                r = etree.parse(str(xmlp)).getroot()
            except Exception as e:
                (self.root / "logs" / "app.log").open("a", encoding="utf-8").write(f"[load_projects] {xmlp}: {e}\n"); continue
            p = Project(id=r.get("id") or uuid.uuid4().hex, name=r.findtext("Name") or d.name, slug=d.name, tracks=[])
            troot = d / "Tracks"
            if troot.exists():
                for td in troot.iterdir():
                    if not td.is_dir(): continue
                    txml = td / "track.xml"
                    if not txml.exists(): continue
                    try:
                        tr = etree.parse(str(txml)).getroot()
                    except Exception as e:
                        (self.root / "logs" / "app.log").open("a", encoding="utf-8").write(f"[load_projects] {txml}: {e}\n"); continue
                    t = Track(
                        id=tr.get("id") or uuid.uuid4().hex, name=tr.findtext("Name") or td.name, slug=td.name,
                        defaults_location=(tr.findtext("Defaults/Location") or ""), defaults_teams_link=(tr.findtext("Defaults/TeamsLink") or ""),
                        roster=[], section_templates=[e.get("name") or "" for e in tr.findall("SectionTemplates/Section")],
                        recurrence_mode=(tr.find("Defaults/Recurrence").get("mode") if tr.find("Defaults/Recurrence") is not None else "weekly"),
                        recurrence_interval=int(tr.find("Defaults/Recurrence").get("interval") if tr.find("Defaults/Recurrence") is not None else 1)
                    )
                    p.tracks.append(t)
            out.append(p)
        return out
