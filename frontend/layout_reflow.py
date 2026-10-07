"""Apply grid positions only when membership or geometry actually changes."""

def place_grid(grid, placements):
    placements = tuple(placements)
    if getattr(grid, '_placement_signature', None) == placements:
        return
    while grid.count():
        grid.takeAt(0)
    for widget,row,column,row_span,column_span in placements:
        grid.addWidget(widget,row,column,row_span,column_span)
    grid._placement_signature = placements

def grid_columns(grid, widgets, columns):
    place_grid(grid, ((w,i//columns,i%columns,1,1) for i,w in enumerate(widgets)))
