import numpy as np

def init_sar_grid(x_min, x_max, y_min, y_max, pixel_size):
    # Calculate number of pixels
    Nx = int((x_max - x_min) / pixel_size)
    Ny = int((y_max - y_min) / pixel_size)

    # Create coordinate axes
    x_axis = np.arange(x_min, x_max, pixel_size)
    y_axis = np.arange(y_min, y_max, pixel_size)

    # Create a 2D grid of coordinates
    X_grid, Y_grid = np.meshgrid(x_axis, y_axis, indexing="xy")

    # Initialise the image grid to hold complex values (for backprojection)
    imageGrid = np.zeros_like(X_grid, dtype=complex)

    print(f"Grid created! The image will be {X_grid.shape[0]} pixels tall by {X_grid.shape[1]} pixels wide.")
    
    return X_grid, Y_grid, imageGrid