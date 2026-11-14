"""Incremental Qt model for the resource detail list."""

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, Qt, Slot


class ResourceListModel(QAbstractListModel):
    resource_role = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent):
        super().__init__(parent)
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def roleNames(self):
        return {self.resource_role: b"resource"}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == self.resource_role and index.isValid() and 0 <= index.row() < len(self.rows):
            return self.rows[index.row()]
        return None

    def update_rows(self, rows):
        parent = QModelIndex()
        target_keys = {row["key"] for row in rows}
        existing = {row["key"] for row in self.rows}
        end = len(self.rows)
        while end:
            if self.rows[end - 1]["key"] in target_keys:
                end -= 1
                continue
            start = end - 1
            while start and self.rows[start - 1]["key"] not in target_keys:
                start -= 1
            self.beginRemoveRows(parent, start, end - 1)
            del self.rows[start:end]
            self.endRemoveRows()
            end = start

        index = 0
        while index < len(rows):
            key = rows[index]["key"]
            if key not in existing:
                end = index + 1
                while end < len(rows) and rows[end]["key"] not in existing:
                    end += 1
                self.beginInsertRows(parent, index, end - 1)
                self.rows[index:index] = rows[index:end]
                self.endInsertRows()
                index = end
                continue
            if self.rows[index]["key"] != key:
                previous = next(i for i in range(index + 1, len(self.rows)) if self.rows[i]["key"] == key)
                self.beginMoveRows(parent, previous, previous, parent, index)
                self.rows.insert(index, self.rows.pop(previous))
                self.endMoveRows()
            if self.rows[index] != rows[index]:
                self.rows[index] = rows[index]
                changed = self.index(index)
                self.dataChanged.emit(changed, changed, [self.resource_role])
            index += 1


class ResourceFilterModel(QSortFilterProxyModel):
    fields = ("category", "episode", "resolution", "fansub")

    def __init__(self, source, parent):
        super().__init__(parent)
        self._filters = ()
        self._season_filter = ""
        self._sort_field = None
        self._descending = False
        self.setSourceModel(source)

    @Slot(str)
    def setSeasonFilter(self, season):
        if self._season_filter != season:
            if hasattr(self, "endFilterChange"):
                self.beginFilterChange()
                self._season_filter = season
                self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
            else:
                self._season_filter = season
                self.invalidateFilter()

    @Slot(str)
    def setSortOrder(self, order):
        fields = {"time": "sort_time", "size": "sort_size", "name": "title"}
        field, _, direction = order.rpartition("_")
        if field not in fields or direction not in {"asc", "desc"}:
            return
        self._sort_field = fields[field]
        self._descending = direction == "desc"
        self.invalidate()
        self.sort(0, Qt.SortOrder.DescendingOrder if self._descending else Qt.SortOrder.AscendingOrder)

    def lessThan(self, left, right):
        first = self.sourceModel().rows[left.row()].get(self._sort_field)
        second = self.sourceModel().rows[right.row()].get(self._sort_field)
        if first is None or second is None:
            return (first is None and second is not None) if self._descending else (
                first is not None and second is None)
        if isinstance(first, str):
            first, second = first.casefold(), second.casefold()
        return first < second

    @Slot(str, str, str, str)
    def setFilters(self, category, episode, resolution, fansub):
        filters = tuple((field, value) for field, value in zip(
            self.fields, (category, episode, resolution, fansub)
        ) if value)
        if self._filters != filters:
            if hasattr(self, "endFilterChange"):
                self.beginFilterChange()
                self._filters = filters
                self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
            else:
                self._filters = filters
                self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        row = self.sourceModel().rows[source_row]
        return (not self._season_filter or self._season_filter in row.get("seasons", ["未知"])) and all(
            row[field] == value for field, value in self._filters)
