from __future__ import annotations
from pathlib import Path
import sys, logging, traceback, uuid, datetime
from PyQt6 import QtCore, QtGui, QtWidgets
from settings import APP_TITLE
from models import Project, Track, MeetingHeader, Meeting, Section, Item
from store import XMLStore, slugify
from ui_editor import EditorPage
from theme import ThemeManager

log = logging.getLogger("pcminutes")
log.setLevel(logging.DEBUG)
if not log.handlers:
    ch = logging.StreamHandler(); ch.setLevel(logging.DEBUG); ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(ch)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.data_root = Path(__file__).resolve().parent / "Data"
        (self.data_root / "logs").mkdir(parents=True, exist_ok=True)
        self.store = XMLStore(self.data_root)
        self.theme = ThemeManager(self.data_root)
        self._build_ui()
        self.theme.apply(QtWidgets.QApplication.instance())

        if not self.store.load_projects():
            self._seed_demo_data()
        self._refresh_nav()

    def _build_ui(self):
        self.resize(1280, 860)
        tb = QtWidgets.QToolBar("Main"); self.addToolBar(tb)
        act_new_proj = tb.addAction("New Project"); act_new_proj.triggered.connect(self.on_new_project)
        act_new_track = tb.addAction("New Track"); act_new_track.triggered.connect(self.on_new_track)
        tb.addSeparator()
        act_new_meeting = tb.addAction("New Meeting"); act_new_meeting.triggered.connect(self.on_new_meeting)
        act_create_next = tb.addAction("Create Next Meeting"); act_create_next.triggered.connect(self.on_create_next)
        act_finalize = tb.addAction("Finalize"); act_finalize.triggered.connect(self.on_finalize)
        act_close = tb.addAction("Close Meeting"); act_close.triggered.connect(self.on_finalize)
        tb.addSeparator()
        act_del_proj = tb.addAction("Delete Project"); act_del_proj.triggered.connect(self.on_delete_project)
        act_del_track = tb.addAction("Delete Track"); act_del_track.triggered.connect(self.on_delete_track)
        act_del_meeting = tb.addAction("Delete Meeting"); act_del_meeting.triggered.connect(self.on_delete_meeting)
        tb.addSeparator()
        act_save = tb.addAction("Save All"); act_save.triggered.connect(self.on_save_all)
        tb.addSeparator()
        self._export_actions: list[QtGui.QAction] = []
        self.act_export_pdf = tb.addAction("Export PDF"); self.act_export_pdf.triggered.connect(self.on_export_pdf); self._export_actions.append(self.act_export_pdf)
        self.act_export_docx = tb.addAction("Export DOCX"); self.act_export_docx.triggered.connect(self.on_export_docx); self._export_actions.append(self.act_export_docx)
        self.act_export_ics = tb.addAction("Export ICS"); self.act_export_ics.triggered.connect(self.on_export_ics); self._export_actions.append(self.act_export_ics)
        tb.addSeparator()
        act_theme = tb.addAction("Light/Dark"); act_theme.triggered.connect(self.on_toggle_theme)

        split = QtWidgets.QSplitter(); split.setOrientation(QtCore.Qt.Orientation.Horizontal); self.setCentralWidget(split)
        self.left = QtWidgets.QTreeWidget(); self.left.setHeaderLabels(["Name","Date"]); self.left.setColumnWidth(0,320)
        split.addWidget(self.left)
        self.center = QtWidgets.QStackedWidget(); split.addWidget(self.center)
        self.placeholder = QtWidgets.QLabel("Select a meeting…"); self.placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.center.addWidget(self.placeholder)
        self.left.currentItemChanged.connect(self._on_nav_selected)
        self.statusBar().showMessage("Ready")
        self._set_export_actions_enabled(False)

    def _current_editor_page(self):
        widget = self.center.currentWidget()
        if isinstance(widget, EditorPage):
            return widget
        if isinstance(widget, QtWidgets.QScrollArea):
            inner = widget.widget()
            if isinstance(inner, EditorPage):
                return inner
        return None

    def _show_editor_page(self, page: EditorPage):
        for idx in reversed(range(1, self.center.count())):
            old = self.center.widget(idx)
            self.center.removeWidget(old)
            old.deleteLater()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.center.addWidget(scroll)
        self.center.setCurrentWidget(scroll)

    def _refresh_nav(self):
        self.left.clear()
        for p in self.store.load_projects():
            p_item = QtWidgets.QTreeWidgetItem([p.name, ""]); p_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("project", p.slug)); self.left.addTopLevelItem(p_item)
            for t in p.tracks:
                t_item = QtWidgets.QTreeWidgetItem([t.name, ""]); t_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("track", p.slug, t.slug)); p_item.addChild(t_item)
                md = self.store.meetings_dir(p, t)
                for d in sorted([x for x in md.iterdir() if x.is_dir() and x.name.isdigit()], key=lambda x:int(x.name)):
                    mxml = self.store.meeting_xml(p, t, d.name)
                    date_text = ""
                    if mxml.exists():
                        try:
                            from lxml import etree
                            r = etree.parse(str(mxml)).getroot()
                            date_text = r.findtext("Header/Date") or ""
                        except Exception: pass
                    m_item = QtWidgets.QTreeWidgetItem([f"Meeting {d.name}", date_text]); m_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("meeting", p.slug, t.slug, d.name))
                    t_item.addChild(m_item)
        self.left.expandAll()
        if self.left.topLevelItemCount():
            p = self.left.topLevelItem(0)
            if p.childCount():
                t = p.child(0)
                if t.childCount():
                    self.left.setCurrentItem(t.child(0))

    def _seed_demo_data(self):
        proj = Project(id=uuid.uuid4().hex, name="Demo Project", slug="demo-project", tracks=[]); self.store.save_project(proj)
        tr = Track(id=uuid.uuid4().hex, name="General Meetings", slug="general-meetings", defaults_location="Boardroom", defaults_teams_link="https://teams.microsoft.com/")
        self.store.save_track(proj, tr)
        header = MeetingHeader(topic="General Meeting", date=datetime.date.today().isoformat(), start="09:00", end="10:00", location="Boardroom", teams_link="https://teams.microsoft.com/")
        m = Meeting(id=uuid.uuid4().hex, number="0001", header=header, sections=[], items=[], finalized_at=None)
        s1 = Section(id=uuid.uuid4().hex, name="General", order=0); s2 = Section(id=uuid.uuid4().hex, name="Schedule", order=1)
        m.sections.extend([s1, s2])
        m.items.append(Item(id=uuid.uuid4().hex, description="Welcome & introductions", status="INFO", assignee_id=None, priority="Normal", due_date=None, tags=[], order=0, section_name="General", notes=[]))
        m.items.append(Item(id=uuid.uuid4().hex, description="Review milestones", status="OPEN", assignee_id=None, priority="Normal", due_date=None, tags=[], order=0, section_name="Schedule", notes=[]))
        self.store.save_meeting(proj, tr, m)

    def _current_context(self):
        item = self.left.currentItem()
        if not item: return None
        return item.data(0, QtCore.Qt.ItemDataRole.UserRole)

    def on_new_project(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip(): return
        self.store.create_project(name.strip())
        self._refresh_nav()

    def on_new_track(self):
        data = self._current_context()
        projects = self.store.load_projects()
        proj = None
        if data and data[0] in ("project","track","meeting"):
            slug = data[1]
            proj = next((x for x in projects if x.slug==slug), None)
            if not proj and data[0] in ("track","meeting"):
                proj = next((x for x in projects if x.slug==data[1]), None)
        if not proj and projects: proj = projects[0]
        if not proj:
            QtWidgets.QMessageBox.warning(self, "No project", "Create a project first."); return
        name, ok = QtWidgets.QInputDialog.getText(self, "New Track", f"Track name for '{proj.name}':")
        if not ok or not name.strip(): return
        self.store.create_track(proj, name.strip())
        self._refresh_nav()

    def on_new_meeting(self):
        data = self._current_context()
        if not data: return
        projects = self.store.load_projects()
        if data[0]=="track":
            proj = next((p for p in projects if p.slug==data[1]), None)
            track = next((t for t in proj.tracks if t.slug==data[2]), None) if proj else None
        elif data[0]=="meeting":
            proj = next((p for p in projects if p.slug==data[1]), None)
            track = next((t for t in proj.tracks if t.slug==data[2]), None) if proj else None
        elif data[0]=="project":
            proj = next((p for p in projects if p.slug==data[1]), None)
            track = proj.tracks[0] if proj and proj.tracks else None
        else:
            return
        if not (proj and track):
            QtWidgets.QMessageBox.warning(self, "Select track", "Select a track (or meeting under a track)."); return
        self.store.create_meeting(proj, track)
        self._refresh_nav()

    def on_create_next(self):
        data = self._current_context()
        if not data: return
        if data[0] not in ("meeting","track"):
            QtWidgets.QMessageBox.information(self, "Select track/meeting", "Select a track or meeting to create the next meeting."); return
        projects = self.store.load_projects()
        if data[0]=="meeting":
            proj = next((p for p in projects if p.slug==data[1]), None); track = next((t for t in proj.tracks if t.slug==data[2]), None) if proj else None
        else:
            proj = next((p for p in projects if p.slug==data[1]), None); track = next((t for t in proj.tracks if t.slug==data[2]), None) if proj else None
        if not (proj and track): return
        self.store.create_next_meeting_respecting_recurrence(proj, track)
        self._refresh_nav()

    def on_finalize(self):
        data = self._current_context()
        if not data or data[0]!="meeting": return
        projects = self.store.load_projects()
        proj = next((p for p in projects if p.slug==data[1]), None)
        track = next((t for t in proj.tracks if t.slug==data[2]), None) if proj else None
        num = data[3]
        if not (proj and track): return
        self.store.finalize_meeting(proj, track, num)
        self._on_nav_selected()

    def on_delete_project(self):
        data = self._current_context()
        if not data or data[0]!="project": 
            QtWidgets.QMessageBox.information(self, "Select project", "Select a project to delete."); return
        slug = data[1]
        if QtWidgets.QMessageBox.question(self, "Delete Project", f"Delete entire project '{slug}' and all its tracks/meetings?", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No) == QtWidgets.QMessageBox.StandardButton.Yes:
            self.store.delete_project(slug); self._refresh_nav()

    def on_delete_track(self):
        data = self._current_context()
        if not data or data[0] not in ("track","meeting"):
            QtWidgets.QMessageBox.information(self, "Select track", "Select a track (or a meeting within it) to delete."); return
        if data[0]=="meeting":
            pslug, tslug = data[1], data[2]
        else:
            pslug, tslug = data[1], data[2]
        if QtWidgets.QMessageBox.question(self, "Delete Track", f"Delete track '{tslug}' and all its meetings?", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No) == QtWidgets.QMessageBox.StandardButton.Yes:
            self.store.delete_track(pslug, tslug); self._refresh_nav()

    def on_delete_meeting(self):
        data = self._current_context()
        if not data or data[0]!="meeting":
            QtWidgets.QMessageBox.information(self, "Select meeting", "Select a meeting to delete."); return
        pslug, tslug, num = data[1], data[2], data[3]
        if QtWidgets.QMessageBox.question(self, "Delete Meeting", f"Delete meeting {num}?", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No) == QtWidgets.QMessageBox.StandardButton.Yes:
            self.store.delete_meeting(pslug, tslug, num); self._refresh_nav()

    def on_save_all(self):
        page = self._current_editor_page()
        if page: page.save()
        QtWidgets.QMessageBox.information(self, "Saved", "All changes saved.")

    def on_toggle_theme(self):
        self.theme.toggle(QtWidgets.QApplication.instance())

    def on_export_pdf(self):
        self._export_current_meeting("pdf")

    def on_export_docx(self):
        self._export_current_meeting("docx")

    def on_export_ics(self):
        self._export_current_meeting("ics")

    def _on_nav_selected(self):
        item = self.left.currentItem()
        if not item: return
        data = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not data: return
        projects = self.store.load_projects()

        if data[0]=="meeting":
            proj = next((p for p in projects if p.slug==data[1]), None)
            track = next((t for t in proj.tracks if t.slug==data[2]), None) if proj else None
            meeting = self.store.load_meeting(proj, track, data[3]) if (proj and track) else None
            if not meeting:
                self._set_export_actions_enabled(False)
                self.center.setCurrentWidget(self.placeholder)
                return
            self._set_export_actions_enabled(True)
            page = EditorPage(self.store, proj, track, meeting)
            self._show_editor_page(page)
            self.statusBar().showMessage(f"Editing {proj.name} / {track.name} / {data[3]}")
        elif data[0]=="track":
            self._set_export_actions_enabled(False)
            if item.childCount():
                self.left.setCurrentItem(item.child(0))
            else:
                self.center.setCurrentWidget(self.placeholder)
        else:
            self._set_export_actions_enabled(False)
            self.center.setCurrentWidget(self.placeholder)

    def _set_export_actions_enabled(self, enabled: bool) -> None:
        for act in getattr(self, "_export_actions", []):
            act.setEnabled(enabled)

    def _export_current_meeting(self, kind: str) -> None:
        data = self._current_context()
        if not data or data[0] != "meeting":
            QtWidgets.QMessageBox.information(self, "Select meeting", "Select a meeting to export.")
            return

        projects = self.store.load_projects()
        proj = next((p for p in projects if p.slug == data[1]), None)
        track = next((t for t in proj.tracks if t.slug == data[2]), None) if proj else None
        if not (proj and track):
            QtWidgets.QMessageBox.warning(self, "Missing data", "Unable to locate the selected meeting.")
            return

        page = self._current_editor_page()
        meeting_obj = None
        if page and page.meeting.number == data[3]:
            page.save()
            meeting_obj = page.meeting
        else:
            meeting_obj = self.store.load_meeting(proj, track, data[3])
        if not meeting_obj:
            QtWidgets.QMessageBox.warning(self, "Missing meeting", "Unable to load meeting details for export.")
            return

        try:
            if kind == "pdf":
                dest = self.store.export_meeting_pdf(proj, track, meeting_obj)
            elif kind == "docx":
                dest = self.store.export_meeting_docx(proj, track, meeting_obj)
            elif kind == "ics":
                dest = self.store.export_meeting_ics(proj, track, meeting_obj)
            else:
                raise ValueError(f"Unsupported export format: {kind}")
        except RuntimeError as exc:
            QtWidgets.QMessageBox.warning(self, "Export unavailable", str(exc))
            return
        except Exception as exc:
            log.exception("Export failed", exc_info=exc)
            QtWidgets.QMessageBox.critical(self, "Export failed", str(exc))
            return

        self.statusBar().showMessage(f"Exported meeting to {dest}")
        QtWidgets.QMessageBox.information(self, "Export complete", f"Export created:\n{dest}")

def main():
    print("Starting QApplication...")
    app = QtWidgets.QApplication(sys.argv)
    try:
        w = MainWindow(); print("MainWindow created")
        w.show()
    except Exception as e:
        print("Exception while creating MainWindow:", e)
        traceback.print_exc()
        mb = QtWidgets.QMessageBox(); mb.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        mb.setWindowTitle("Startup error"); mb.setText(str(e)); mb.setDetailedText(traceback.format_exc()); mb.exec()
        return 1
    rc = app.exec(); print("QApplication exited with code", rc); return rc

if __name__ == "__main__":
    sys.exit(main())
