class PaginationError(ValueError):
    def __init__(self, params):
        page = params[0]
        max_page = params[1]
        if max_page != 0:
            self.message = f"Invalid Page: `{page}`. Pages range from `1` to `{max_page}`"
        else:
            self.message = f"Invalid Page: `{page}`. There are no pages of data to display."
        super().__init__(self.message)
        print(self.message)
