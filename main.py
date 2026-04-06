import ttkbootstrap as tb
from gui.dashboard import SARDashboard

def main():
    app = tb.Window(themename='superhero')
    gui = SARDashboard(app)
    app.mainloop()

if __name__ == "__main__":
    main()
