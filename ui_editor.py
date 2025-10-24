from __future__ import annotations
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
import uuid
from datetime import datetime
from models import Meeting, MeetingHeader, Project, Track, Section, Item, Note

class DraggableList(QtWidgets.QListWidget):
    moved = QtCore.pyqtSignal()
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(6)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizeAdjustPolicy(QtWidgets.QAbstractItemView.SizeAdjustPolicy.AdjustToContents)
    def dropEvent(self, e: QtGui.QDropEvent) -> None:
        super().dropEvent(e); self.moved.emit()

class ItemForm(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()
    def __init__(self, it: Item, parent=None):
        super().__init__(parent)
        self.it = it
        grid = QtWidgets.QGridLayout(self); grid.setContentsMargins(4,4,4,4)
        self.e_desc = QtWidgets.QLineEdit(it.description); self.e_desc.textChanged.connect(self.changed)
        self.e_status = QtWidgets.QComboBox(); self.e_status.addItems(["OPEN","INFO","CLOSED"]); self.e_status.setCurrentText(it.status); self.e_status.currentTextChanged.connect(self.changed)
        self.e_assignee = QtWidgets.QLineEdit(it.assignee_id or ""); self.e_assignee.textChanged.connect(self.changed)
        self.e_priority = QtWidgets.QComboBox(); self.e_priority.addItems(["Low","Normal","High"]); self.e_priority.setCurrentText(it.priority); self.e_priority.currentTextChanged.connect(self.changed)
        self.e_due = QtWidgets.QDateEdit(); self.e_due.setDisplayFormat("yyyy-MM-dd"); self.e_due.setCalendarPopup(True)
        try:
            if it.due_date:
                y,m,d = [int(x) for x in it.due_date.split("-")]; self.e_due.setDate(QtCore.QDate(y,m,d))
        except: pass
        self.e_due.dateChanged.connect(self.changed)
        self.e_tags = QtWidgets.QLineEdit(",".join(it.tags)); self.e_tags.textChanged.connect(self.changed)

        r=0
        grid.addWidget(QtWidgets.QLabel("Description"), r,0); grid.addWidget(self.e_desc, r,1,1,5); r+=1
        grid.addWidget(QtWidgets.QLabel("Status"), r,0); grid.addWidget(self.e_status, r,1)
        grid.addWidget(QtWidgets.QLabel("Assignee"), r,2); grid.addWidget(self.e_assignee, r,3)
        grid.addWidget(QtWidgets.QLabel("Priority"), r,4); grid.addWidget(self.e_priority, r,5); r+=1
        grid.addWidget(QtWidgets.QLabel("Due"), r,0); grid.addWidget(self.e_due, r,1)
        grid.addWidget(QtWidgets.QLabel("Tags"), r,2); grid.addWidget(self.e_tags, r,3,1,3)

        self.notes = QtWidgets.QListWidget()
        for n in sorted(it.notes, key=lambda n:n.created_at, reverse=True):
            self.notes.addItem(f"{n.meeting_date} — {n.text}")
        self.new_note = QtWidgets.QTextEdit(); self.new_note.setPlaceholderText("Add note…")
        self.btn_add = QtWidgets.QPushButton("Add Note")
        self.btn_add.clicked.connect(self._add_note)

        grid.addWidget(QtWidgets.QLabel("Notes"), r+1,0); grid.addWidget(self.notes, r+1,1,1,5)
        grid.addWidget(self.new_note, r+2,0,1,5); grid.addWidget(self.btn_add, r+2,5)

    def _add_note(self):
        text = self.new_note.toPlainText().strip()
        if not text: return
        self.it.notes.append(Note(id=uuid.uuid4().hex, text=text, meeting_date=datetime.now().date().isoformat(), created_at=datetime.now().isoformat(timespec="seconds")))
        self.notes.insertItem(0, f"{self.it.notes[0].meeting_date} — {text}")
        self.new_note.clear()
        self.changed.emit()

    def apply(self):
        self.it.description = self.e_desc.text().strip()
        self.it.status = self.e_status.currentText()
        self.it.assignee_id = self.e_assignee.text().strip() or None
        self.it.priority = self.e_priority.currentText()
        self.it.due_date = self.e_due.date().toString("yyyy-MM-dd") if self.e_due.date().isValid() else None
        self.it.tags = [t.strip() for t in self.e_tags.text().split(",") if t.strip()]

class ItemCard(QtWidgets.QFrame):
    changed = QtCore.pyqtSignal()
    toggled = QtCore.pyqtSignal(bool)
    resized = QtCore.pyqtSignal()
    def __init__(self, it: Item, parent=None):
        super().__init__(parent); self.it = it
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel); self.setObjectName("ItemCard")
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(8,8,8,8); v.setSpacing(6)
        head = QtWidgets.QHBoxLayout(); head.setContentsMargins(0,0,0,0)
        self.toggle = QtWidgets.QToolButton(); self.toggle.setCheckable(True); self.toggle.setChecked(True)
        self.toggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toggle.setArrowType(QtCore.Qt.ArrowType.DownArrow)
        self.toggle.setAutoRaise(True)
        self.toggle.setToolTip("Collapse or expand this item")
        self.title = QtWidgets.QLabel(it.description or "Agenda item")
        self.title.setObjectName("ItemTitle")
        self.summary = QtWidgets.QLabel(self._summary_text())
        self.summary.setObjectName("ItemSummary")
        self.summary.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.summary.setWordWrap(True)
        self.summary.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.summary.hide()
        head.addWidget(self.toggle)
        head.addWidget(self.title, 1)
        head.addWidget(self.summary, 2)
        v.addLayout(head)

        self.body = QtWidgets.QFrame()
        body_layout = QtWidgets.QVBoxLayout(self.body)
        body_layout.setContentsMargins(0,0,0,0); body_layout.setSpacing(6)
        self.form = ItemForm(it); self.form.changed.connect(self._on_form_changed)
        body_layout.addWidget(self.form)
        v.addWidget(self.body)
        self.toggle.toggled.connect(self._on_toggle)
        self.body.setMinimumHeight(0)
        self.body.setMaximumHeight(self.body.sizeHint().height())

        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QtCore.QEasingCurve.Type.InOutCubic)
        self._animation.valueChanged.connect(self._apply_animation_height)
        self._animation.finished.connect(self._animation_finished)

    def _on_toggle(self, on: bool):
        self.toggle.setArrowType(QtCore.Qt.ArrowType.DownArrow if on else QtCore.Qt.ArrowType.RightArrow)
        self.summary.setText(self._summary_text())
        self.summary.setVisible(not on)
        self.title.setVisible(on)
        if on:
            self.body.setVisible(True)
        start = self.body.maximumHeight()
        end = self.body.layout().sizeHint().height() if on else 0
        self._animation.stop()
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()
        self.toggled.emit(on)

    def apply(self):
        self.form.apply()
        self.title.setText(self.it.description or "Agenda item")
        self.summary.setText(self._summary_text())

    def _summary_text(self) -> str:
        desc = self.it.description or "Agenda item"
        status = self.it.status or ""
        due = self.it.due_date or "No due date"
        assignee = self.it.assignee_id or "Unassigned"
        return f"{desc} — Status: {status} — Due: {due} — Owner: {assignee}"

    def _apply_animation_height(self, value):
        self.body.setMaximumHeight(int(value))
        self.body.updateGeometry()
        self.updateGeometry()
        self.resized.emit()

    def _animation_finished(self):
        if self.body.maximumHeight() == 0:
            self.body.setVisible(False)
        else:
            self.body.setVisible(True)
        self.resized.emit()

    def _on_form_changed(self):
        self.form.apply()
        self.title.setText(self.it.description or "Agenda item")
        self.summary.setText(self._summary_text())
        self.changed.emit()

class SectionWidget(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()
    def __init__(self, section: Section, items: list[Item], parent=None):
        super().__init__(parent); self.section = section; self._items = items; self._list_item = None
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(6,6,6,6); v.setSpacing(6)
        header = QtWidgets.QHBoxLayout()
        self.ed_title = QtWidgets.QLineEdit(section.name); self.ed_title.setPlaceholderText("Section title")
        self.btn_collapse = QtWidgets.QToolButton(text="Collapse"); self.btn_collapse.setCheckable(True); self.btn_collapse.setChecked(True)
        self.btn_add_item = QtWidgets.QPushButton("+ Add Item")
        header.addWidget(self.ed_title, 1); header.addStretch(1); header.addWidget(self.btn_collapse); header.addWidget(self.btn_add_item)
        v.addLayout(header)

        self.list = DraggableList()
        for it in sorted(items, key=lambda x:x.order):
            lw = QtWidgets.QListWidgetItem()
            card = ItemCard(it); card.changed.connect(self.changed)
            card.changed.connect(self._update_height)
            card.toggled.connect(lambda _on, c=card: self._on_card_toggled(c))
            card.resized.connect(self._update_height)
            lw.setSizeHint(card.sizeHint())
            self.list.addItem(lw); self.list.setItemWidget(lw, card)
        v.addWidget(self.list)
        self.list.moved.connect(self._renumber_items)

        self.btn_collapse.toggled.connect(self._on_section_collapse)
        self.btn_add_item.clicked.connect(self._add_item)
        self.ed_title.textChanged.connect(self.changed)
        QtCore.QTimer.singleShot(0, self._update_height)

    def attach_list_item(self, item: QtWidgets.QListWidgetItem):
        self._list_item = item
        QtCore.QTimer.singleShot(0, self._update_size_hint)

    def _add_item(self):
        it = Item(id=uuid.uuid4().hex, description="New agenda item", status="OPEN", assignee_id=None, priority="Normal", due_date=None, tags=[], order=self.list.count(), section_name=self.section.name, notes=[])
        self._items.append(it)
        lw = QtWidgets.QListWidgetItem()
        card = ItemCard(it); card.changed.connect(self.changed)
        card.changed.connect(self._update_height)
        card.toggled.connect(lambda _on, c=card: self._on_card_toggled(c))
        card.resized.connect(self._update_height)
        lw.setSizeHint(card.sizeHint())
        self.list.addItem(lw); self.list.setItemWidget(lw, card)
        self.changed.emit()
        QtCore.QTimer.singleShot(0, self._update_height)

    def _renumber_items(self):
        for i in range(self.list.count()):
            card = self.list.itemWidget(self.list.item(i))
            card.it.order = i
        self.changed.emit()
        self._update_height()

    def apply(self) -> list[Item]:
        self.section.name = self.ed_title.text().strip() or self.section.name
        collected: list[Item] = []
        for i in range(self.list.count()):
            card = self.list.itemWidget(self.list.item(i))
            if card: card.apply()
            card.it.section_name = self.section.name
            card.it.order = i
            collected.append(card.it)
        return collected

    def _update_height(self):
        if not self.list.isVisible():
            total = 0
        else:
            total = self.list.contentsMargins().top() + self.list.contentsMargins().bottom()
            spacing = self.list.spacing()
            for i in range(self.list.count()):
                item = self.list.item(i)
                card = self.list.itemWidget(item)
                if not card:
                    continue
                hint = max(card.sizeHint().height(), card.height())
                total += hint
                if i:
                    total += spacing
                item.setSizeHint(card.sizeHint())
        self.list.setFixedHeight(total)
        self.list.updateGeometry()
        self._update_size_hint()

    def _on_card_toggled(self, card: ItemCard):
        self._update_height()
        card.summary.setText(card._summary_text())

    def _on_section_collapse(self, expand: bool):
        self.btn_collapse.setText("Collapse" if expand else "Expand")
        self.list.setVisible(expand)
        QtCore.QTimer.singleShot(0, self._update_height)

    def _update_size_hint(self):
        if not self._list_item:
            return
        hint = self.sizeHint()
        self._list_item.setSizeHint(hint)
        self.updateGeometry()
        parent = self.parent()
        while parent and not isinstance(parent, QtWidgets.QListWidget):
            parent = parent.parent()
        if isinstance(parent, QtWidgets.QListWidget):
            parent.updateGeometries()

class EditorPage(QtWidgets.QWidget):
    requestSave = QtCore.pyqtSignal()
    def __init__(self, store, project: Project, track: Track, meeting: Meeting, parent=None):
        super().__init__(parent); self.store, self.project, self.track, self.meeting = store, project, track, meeting
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(12)

        header = QtWidgets.QGroupBox("Meeting Header")
        g = QtWidgets.QGridLayout(header)
        self.ed_topic = QtWidgets.QLineEdit(meeting.header.topic)
        self.ed_date  = QtWidgets.QDateEdit(); self.ed_date.setCalendarPopup(True); self.ed_date.setDisplayFormat("yyyy-MM-dd")
        try:
            y,m,d = [int(x) for x in (meeting.header.date or "").split("-")]
            if y and m and d: self.ed_date.setDate(QtCore.QDate(y,m,d))
            else: self.ed_date.setDate(QtCore.QDate.currentDate())
        except: self.ed_date.setDate(QtCore.QDate.currentDate())
        def _qtime(s, default):
            t = QtCore.QTime.fromString(s or default, "hh:mm"); return t if t.isValid() else QtCore.QTime.fromString(default, "hh:mm")
        self.ed_start = QtWidgets.QTimeEdit(_qtime(meeting.header.start, "09:00")); self.ed_end = QtWidgets.QTimeEdit(_qtime(meeting.header.end, "10:00"))
        self.ed_loc = QtWidgets.QLineEdit(meeting.header.location or ""); self.ed_link = QtWidgets.QLineEdit(meeting.header.teams_link or "")
        r=0
        g.addWidget(QtWidgets.QLabel("Topic:"), r,0); g.addWidget(self.ed_topic, r,1,1,3); r+=1
        g.addWidget(QtWidgets.QLabel("Date:"), r,0); g.addWidget(self.ed_date, r,1); g.addWidget(QtWidgets.QLabel("Start:"), r,2); g.addWidget(self.ed_start, r,3); r+=1
        g.addWidget(QtWidgets.QLabel("End:"), r,2); g.addWidget(self.ed_end, r,3)
        g.addWidget(QtWidgets.QLabel("Location:"), r,0); g.addWidget(self.ed_loc, r,1,1,3); r+=1
        g.addWidget(QtWidgets.QLabel("Teams link:"), r,0); g.addWidget(self.ed_link, r,1,1,3); r+=1
        lay.addWidget(header)

        self.section_list = DraggableList()
        lay.addWidget(self.section_list, 1)

        for s in sorted(meeting.sections, key=lambda x:x.order):
            lw = QtWidgets.QListWidgetItem()
            items = [i for i in meeting.items if i.section_name==s.name]
            widget = SectionWidget(s, items); widget.changed.connect(self.requestSave.emit)
            lw.setSizeHint(widget.sizeHint())
            self.section_list.addItem(lw); self.section_list.setItemWidget(lw, widget)
            widget.attach_list_item(lw)

        self.section_list.moved.connect(self._renumber_sections)

        controls = QtWidgets.QHBoxLayout()
        self.btn_add_section = QtWidgets.QPushButton("+ Add Section")
        self.btn_expand_all = QtWidgets.QPushButton("Expand All Sections")
        self.btn_collapse_all = QtWidgets.QPushButton("Collapse All Sections")
        controls.addWidget(self.btn_add_section); controls.addStretch(1); controls.addWidget(self.btn_expand_all); controls.addWidget(self.btn_collapse_all)
        lay.addLayout(controls)

        for w in (self.ed_topic, self.ed_loc, self.ed_link): w.textChanged.connect(self.requestSave.emit)
        self.ed_date.dateChanged.connect(self.requestSave.emit); self.ed_start.timeChanged.connect(self.requestSave.emit); self.ed_end.timeChanged.connect(self.requestSave.emit)
        self.btn_add_section.clicked.connect(self._add_section)
        self.btn_expand_all.clicked.connect(lambda: self._set_all_sections(True))
        self.btn_collapse_all.clicked.connect(lambda: self._set_all_sections(False))

        self.requestSave.connect(self.save)

        if meeting.finalized_at: self.setDisabled(True)

    def _renumber_sections(self):
        for i in range(self.section_list.count()):
            w = self.section_list.itemWidget(self.section_list.item(i))
            w.section.order = i
        self.requestSave.emit()

    def _add_section(self):
        order = self.section_list.count()
        s = Section(id=uuid.uuid4().hex, name="New Section", order=order)
        self.meeting.sections.append(s)
        lw = QtWidgets.QListWidgetItem()
        widget = SectionWidget(s, []); widget.changed.connect(self.requestSave.emit)
        lw.setSizeHint(widget.sizeHint())
        self.section_list.addItem(lw); self.section_list.setItemWidget(lw, widget)
        widget.attach_list_item(lw)
        self.requestSave.emit()

    def _set_all_sections(self, expand: bool):
        for i in range(self.section_list.count()):
            w = self.section_list.itemWidget(self.section_list.item(i))
            if w.btn_collapse.isChecked() != expand:
                w.btn_collapse.setChecked(expand)
            else:
                w._on_section_collapse(expand)

    def save(self):
        h = self.meeting.header
        h.topic = self.ed_topic.text().strip()
        h.date = self.ed_date.date().toString("yyyy-MM-dd")
        h.start = self.ed_start.time().toString("hh:mm")
        h.end = self.ed_end.time().toString("hh:mm")
        h.location = self.ed_loc.text().strip()
        h.teams_link = self.ed_link.text().strip()

        aggregated: list[Item] = []
        for i in range(self.section_list.count()):
            w = self.section_list.itemWidget(self.section_list.item(i))
            w.section.order = i
            aggregated.extend(w.apply())

        self.meeting.items = aggregated

        self.store.save_meeting(self.project, self.track, self.meeting)
