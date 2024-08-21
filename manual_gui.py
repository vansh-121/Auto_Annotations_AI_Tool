import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from tkinter import ttk
from PIL import Image, ImageTk
import cv2
import os
import shutil
import random
import tkinter.colorchooser as colorchooser
import tkinter.simpledialog as simpledialog

class AnnotationTool:
    def __init__(self, root, dataset_path):
        self.root = root
        self.root.title("Image Annotation Tool")

        self.dataset_path = dataset_path
        self.image_folder = os.path.join(dataset_path, "images")
        self.label_folder = os.path.join(dataset_path, "labels")
        self.null_folder = os.path.join(dataset_path, "null")
        os.makedirs(self.null_folder, exist_ok=True)

        self.image_files = [f for f in os.listdir(self.image_folder) if f.endswith(('jpg', 'jpeg', 'png'))]
        self.current_image_index = 0
        self.annotations = []
        self.classes = {}
        self.class_colors = {}
        self.current_class = None

        self.zoom_factor = 1.0  # Initial zoom level
        self.zoom_step = 1.2    # Factor by which zoom will increase/decrease
        self.zoom_min = 0.5     # Minimum zoom factor
        self.zoom_max = 3.0     # Maximum zoom factor

        self.prompt_for_classes()

        self.canvas_width = 1200
        self.canvas_height = 900
        self.canvas = tk.Canvas(root, cursor="cross", width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.class_list_frame = tk.Frame(root)
        self.class_list_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.class_listbox = tk.Listbox(self.class_list_frame, height=20)
        self.class_listbox.pack(side=tk.TOP, fill=tk.Y, expand=True)
        self.class_listbox.bind('<<ListboxSelect>>', self.on_class_select)

        self.populate_class_listbox()

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Button-3>", self.on_right_click)

        self.rect = None
        self.start_x = None
        self.start_y = None
        self.selected_bbox = None
        self.selected_handle = None
        self.selected_edge = None
        self.handle_size = 20

        self.load_image()

        self.control_frame = tk.Frame(root)
        self.control_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.prev_button = tk.Button(self.control_frame, text="<< Previous", command=self.prev_image)
        self.prev_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.next_button = tk.Button(self.control_frame, text="Next >>", command=self.next_image)
        self.next_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.new_class_button = tk.Button(self.control_frame, text="Add New Class", command=self.add_new_class)
        self.new_class_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.delete_annotations_button = tk.Button(self.control_frame, text="Delete All Annotations", command=self.delete_annotations)
        self.delete_annotations_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.mark_as_null_button = tk.Button(self.control_frame, text="Mark as Null", command=self.mark_as_null)
        self.mark_as_null_button.pack(side=tk.LEFT, padx=10, pady=10)

        # Bind zoom actions
        self.root.bind("<Control-MouseWheel>", self.on_mouse_wheel)

        self.root.bind("<Control-n>", lambda event: self.add_new_class())
        self.root.bind("<Delete>", lambda event: self.delete_annotations())
        self.root.bind("n", lambda event: self.mark_as_null())
        self.root.bind("<Left>", self.on_left_arrow)
        self.root.bind("<Right>", self.on_right_arrow)


        self.statistics_button = tk.Button(self.control_frame, text="Statistics", command=self.show_statistics)
        self.statistics_button.pack(side=tk.LEFT, padx=10, pady=10)


    def show_statistics(self):
        total_images = len(self.image_files)
        total_annotated_images = 0
        class_count = {class_name: 0 for class_name in self.classes}

        for image_file in self.image_files:
            label_filename = os.path.basename(image_file).replace('.jpg', '.txt').replace('.jpeg', '.txt').replace('.png', '.txt')
            label_path = os.path.join(self.label_folder, label_filename)
            if os.path.exists(label_path):
                total_annotated_images += 1
                with open(label_path, 'r') as file:
                    lines = file.readlines()
                    for line in lines:
                        class_index = int(line.strip().split()[0])
                        class_name = next((name for name, index in self.classes.items() if index == class_index), None)
                        if class_name:
                            class_count[class_name] += 1

        message = f"Total No of images: {total_images}\n"
        message += f"Total Annotated Images: {total_annotated_images}\n"
        for class_name, count in class_count.items():
            message += f"Total Annotated Images of {class_name}: {count}\n"

        messagebox.showinfo("Statistics", message)

    def on_left_arrow(self, event):
        self.prev_image()

    def on_right_arrow(self, event):
        self.next_image()

    def prompt_for_classes(self):
        while True:
            class_name = simpledialog.askstring("Class Input", "Enter class name (or leave blank to finish):")
            if not class_name:
                break
            class_index = simpledialog.askinteger("Class Index", f"Enter index for class '{class_name}':")
            if class_index is not None:
                self.classes[class_name] = class_index
                self.class_colors[class_index] = self.random_color()

    def populate_class_listbox(self):
        self.class_listbox.delete(0, tk.END)
        for class_name, class_index in self.classes.items():
            self.class_listbox.insert(tk.END, f"{class_index}: {class_name}")

    def on_class_select(self, event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            class_item = event.widget.get(index)
            class_index, class_name = class_item.split(": ")
            self.current_class = class_name.strip()

    def load_image(self):
        if self.current_image_index >= len(self.image_files):
            messagebox.showinfo("Info", "No more images to annotate.")
            return

        self.image_path = os.path.join(self.image_folder, self.image_files[self.current_image_index])
        print(f"Trying to load image from: {self.image_path}")

        if not os.path.exists(self.image_path):
            messagebox.showerror("Error", f"File does not exist: {self.image_path}")
            return

        img = cv2.imread(self.image_path)
        if img is None:
            messagebox.showerror("Error", f"Failed to read image: {self.image_path}")
            return

        self.image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.image = cv2.resize(self.image, (self.canvas_width, self.canvas_height))
        self.tk_image = ImageTk.PhotoImage(Image.fromarray(self.image))

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        self.load_annotations()

    def load_annotations(self):
        if self.current_image_index >= len(self.image_files):
            messagebox.showinfo("Info", "No more images to annotate.")
            return

        self.image_path = os.path.join(self.image_folder, self.image_files[self.current_image_index])
        self.image = cv2.cvtColor(cv2.imread(self.image_path), cv2.COLOR_BGR2RGB)

        self.image = cv2.resize(self.image, (self.canvas_width, self.canvas_height))
        self.tk_image = ImageTk.PhotoImage(Image.fromarray(self.image))

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        label_filename = os.path.basename(self.image_path).replace('.jpg', '.txt').replace('.jpeg', '.txt').replace('.png', '.txt')
        label_path = os.path.join(self.label_folder, label_filename)
        self.annotations = []
        if os.path.exists(label_path):
            with open(label_path, 'r') as file:
                lines = file.readlines()
                for line in lines:
                    class_index, center_x, center_y, width, height = map(float, line.strip().split())
                    bbox = {
                        'class_index': int(class_index),
                        'center_x': center_x,
                        'center_y': center_y,
                        'width': width,
                        'height': height
                    }
                    self.annotations.append(bbox)
            self.ensure_classes_initialized()
            self.draw_annotations()

    def save_annotations(self):
        label_filename = os.path.basename(self.image_path).replace('.jpg', '.txt').replace('.jpeg', '.txt').replace('.png', '.txt')
        label_path = os.path.join(self.label_folder, label_filename)

        with open(label_path, 'w') as file:
            for bbox in self.annotations:
                class_index = bbox['class_index']
                center_x = bbox['center_x']
                center_y = bbox['center_y']
                width = bbox['width']
                height = bbox['height']
                line = f"{class_index} {center_x} {center_y} {width} {height}\n"
                file.write(line)

    def add_new_class(self):
        class_name = simpledialog.askstring("Input", "Enter new class name:")
        if class_name:
            self.current_class = class_name
            self.update_classes()
            self.populate_class_listbox()

    def update_classes(self):
        if self.current_class and self.current_class not in self.classes:
            class_index = len(self.classes)
            self.classes[self.current_class] = class_index
            self.class_colors[class_index] = self.random_color()

    def ensure_classes_initialized(self):
        for bbox in self.annotations:
            class_index = bbox['class_index']
            if class_index not in self.class_colors:
                class_name = f"class_{class_index}"
                self.classes[class_name] = class_index
                self.class_colors[class_index] = self.random_color()

    def random_color(self):
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))

    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.selected_bbox = self.find_bbox(event.x, event.y)
        if self.selected_bbox:
            self.selected_handle = self.find_handle(event.x, event.y, self.selected_bbox)
            self.selected_edge = self.find_edge(event.x, event.y, self.selected_bbox)
        else:
            self.selected_handle = None
            self.selected_edge = None
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red')

    def on_drag(self, event):
        cur_x, cur_y = (event.x, event.y)
        if self.selected_handle:
            self.resize_bbox(event.x, event.y, self.selected_bbox, self.selected_handle)
        elif self.selected_edge:
            self.resize_bbox(event.x, event.y, self.selected_bbox, self.selected_edge)
        else:
            self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_wheel(self, event):
        if event.delta > 0:  # Zoom in
            self.zoom_factor = min(self.zoom_factor * self.zoom_step, self.zoom_max)
        elif event.delta < 0:  # Zoom out
            self.zoom_factor = max(self.zoom_factor / self.zoom_step, self.zoom_min)

        self.update_image_and_annotations()


    def on_release(self, event):
        self.canvas.config(cursor="cross")
        if not self.selected_handle and not self.selected_edge:
            end_x, end_y = (event.x, event.y)
            width = abs(end_x - self.start_x)
            height = abs(end_y - self.start_y)
            center_x = (self.start_x + end_x) / 2 / self.canvas_width
            center_y = (self.start_y + end_y) / 2 / self.canvas_height

            if self.current_class is None:
                self.add_new_class()

            if self.current_class:
                self.update_classes()
                class_index = self.classes[self.current_class]
                bbox = {
                    'class_index': class_index,
                    'center_x': center_x,
                    'center_y': center_y,
                    'width': width / self.canvas_width,
                    'height': height / self.canvas_height
                }
                self.annotations.append(bbox)
                self.save_annotations()
                self.draw_annotations()
        self.rect = None
        self.selected_bbox = None
        self.selected_handle = None
        self.selected_edge = None

    def on_mouse_wheel(self, event):
        # Update zoom factor based on the mouse wheel movement
        if event.delta > 0:
            self.zoom_factor = min(self.zoom_factor * self.zoom_step, self.zoom_max)
        else:
            self.zoom_factor = max(self.zoom_factor / self.zoom_step, self.zoom_min)
    
        # Reload the image and redraw annotations with the updated zoom factor
        self.update_image_and_annotations()

    def update_image_and_annotations(self):
        self.load_image()  # Reloads the image with the updated zoom factor
        self.draw_annotations()  # Redraw annotations with the updated zoom factor
    

    def on_motion(self, event):
        if self.find_handle(event.x, event.y, self.find_bbox(event.x, event.y)):
            self.canvas.config(cursor="fleur")
        elif self.find_edge(event.x, event.y, self.find_bbox(event.x, event.y)):
            self.canvas.config(cursor="sb_h_double_arrow")
        else:
            self.canvas.config(cursor="cross")

    def resize_bbox(self, x, y, bbox, handle):
        cx, cy, w, h = bbox['center_x'], bbox['center_y'], bbox['width'], bbox['height']
        left = (cx - w/2) * self.canvas_width * self.zoom_factor
        right = (cx + w/2) * self.canvas_width * self.zoom_factor
        top = (cy - h/2) * self.canvas_height * self.zoom_factor
        bottom = (cy + h/2) * self.canvas_height * self.zoom_factor

        if handle == "left":
            left = min(max(0, x), right - 10)/ self.zoom_factor
        elif handle == "right":
            right = max(min(self.canvas_width, x), left + 10)/ self.zoom_factor
        elif handle == "top":
            top = min(max(0, y), bottom - 10)/ self.zoom_factor
        elif handle == "bottom":
            bottom = max(min(self.canvas_height, y), top + 10)/ self.zoom_factor
        elif handle == "top_left":
            left = min(max(0, x), right - 10)/ self.zoom_factor
            top = min(max(0, y), bottom - 10)/ self.zoom_factor
        elif handle == "top_right":
            right = max(min(self.canvas_width, x), left + 10)/ self.zoom_factor
            top = min(max(0, y), bottom - 10)/ self.zoom_factor
        elif handle == "bottom_left":
            left = min(max(0, x), right - 10)/ self.zoom_factor
            bottom = max(min(self.canvas_height, y), top + 10)/ self.zoom_factor
        elif handle == "bottom_right":
            right = max(min(self.canvas_width, x), left + 10)/ self.zoom_factor
            bottom = max(min(self.canvas_height, y), top + 10)/ self.zoom_factor

        center_x = (left + right) / 2 / (self.canvas_width * self.zoom_factor)
        center_y = (top + bottom) / 2 / (self.canvas_height * self.zoom_factor)
        width = abs(right - left) / (self.canvas_width * self.zoom_factor)
        height = abs(bottom - top) / (self.canvas_height * self.zoom_factor)

        bbox['center_x'] = center_x
        bbox['center_y'] = center_y
        bbox['width'] = width
        bbox['height'] = height

        self.save_annotations()
        self.draw_annotations()

    def find_bbox(self, x, y):
        for bbox in self.annotations:
            cx, cy, w, h = bbox['center_x'], bbox['center_y'], bbox['width'], bbox['height']
            left = (cx - w/2) * self.canvas_width
            right = (cx + w/2) * self.canvas_width
            top = (cy - h/2) * self.canvas_height
            bottom = (cy + h/2) * self.canvas_height

            if left <= x <= right and top <= y <= bottom:
                return bbox
        return None

    def find_handle(self, x, y, bbox):
        cx, cy, w, h = bbox['center_x'], bbox['center_y'], bbox['width'], bbox['height']
        left = (cx - w/2) * self.canvas_width
        right = (cx + w/2) * self.canvas_width
        top = (cy - h/2) * self.canvas_height
        bottom = (cy + h/2) * self.canvas_height

        if abs(x - left) < self.handle_size:
            if abs(y - top) < self.handle_size:
                return "top_left"
            if abs(y - bottom) < self.handle_size:
                return "bottom_left"
            return "left"
        if abs(x - right) < self.handle_size:
            if abs(y - top) < self.handle_size:
                return "top_right"
            if abs(y - bottom) < self.handle_size:
                return "bottom_right"
            return "right"
        if abs(y - top) < self.handle_size:
            return "top"
        if abs(y - bottom) < self.handle_size:
            return "bottom"

        return None

    def find_edge(self, x, y, bbox):
        handle = self.find_handle(x, y, bbox)
        if handle:
            return handle

        return None

    def draw_annotations(self):
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        for bbox in self.annotations:
            cx, cy, w, h = bbox['center_x'], bbox['center_y'], bbox['width'], bbox['height']
            left = (cx - w/2) * self.canvas_width
            right = (cx + w/2) * self.canvas_width
            top = (cy - h/2) * self.canvas_height
            bottom = (cy + h/2) * self.canvas_height
            class_index = bbox['class_index']
            class_name = next((k for k, v in self.classes.items() if v == class_index), "Unknown")
            color = self.class_colors.get(class_index, "#000000")
            self.canvas.create_rectangle(left, top, right, bottom, outline=color, width=2)
            self.canvas.create_text(left, top, anchor=tk.SW, text=class_name, fill=color, font=("Arial", 12, "bold"))

    def on_motion(self, event):
        x, y = event.x, event.y
        self.canvas.config(cursor="cross")

        for bbox in self.annotations:
            handle = self.find_handle(x, y, bbox)
            if handle:
                if handle == "left" or handle == "right":
                    self.canvas.config(cursor="sb_h_double_arrow")
                elif handle == "top" or handle == "bottom":
                    self.canvas.config(cursor="sb_v_double_arrow")
                elif handle == "top_left" or handle == "bottom_right":
                    self.canvas.config(cursor="sizing")
                elif handle == "top_right" or handle == "bottom_left":
                    self.canvas.config(cursor="sizing")
                return


    
    def on_right_click(self, event):
        bbox = self.find_bbox(event.x, event.y)
        if bbox:
            self.show_annotation_options_dialog(bbox)

    def show_annotation_options_dialog(self, bbox):
        cx, cy, w, h = bbox['center_x'], bbox['center_y'], bbox['width'], bbox['height']
        left = (cx - w/2) * self.canvas_width
        right = (cx + w/2) * self.canvas_width
        top = (cy - h/2) * self.canvas_height
        bottom = (cy + h/2) * self.canvas_height

        dialog = tk.Toplevel(self.root)
        dialog.title("Annotation Options")
        dialog.geometry(f"+{int(self.root.winfo_rootx() + right)}+{int(self.root.winfo_rooty() + bottom)}")

        tk.Button(dialog, text="Delete Annotation", command=lambda: self.delete_annotation(bbox, dialog)).pack(padx=10, pady=5)
        tk.Button(dialog, text="Change Class", command=lambda: self.change_class(bbox, dialog)).pack(padx=10, pady=5)
        tk.Button(dialog, text="Save and Exit", command=dialog.destroy).pack(padx=10, pady=5)


    def delete_annotations(self):
        self.annotations = []
        self.save_annotations()
        self.draw_annotations()


    def delete_annotation(self, bbox, dialog = None):
        self.annotations.remove(bbox)
        self.save_annotations()
        self.draw_annotations()
        if dialog:
            dialog.destroy()

    def show_annotation_options_dialog(self, bbox):
        cx, cy, w, h = bbox['center_x'], bbox['center_y'], bbox['width'], bbox['height']
        left = (cx - w/2) * self.canvas_width
        right = (cx + w/2) * self.canvas_width
        top = (cy - h/2) * self.canvas_height
        bottom = (cy + h/2) * self.canvas_height

        dialog = tk.Toplevel(self.root)
        dialog.title("Annotation Options")
        dialog.geometry(f"+{int(self.root.winfo_rootx() + right)}+{int(self.root.winfo_rooty() + bottom)}")

        tk.Button(dialog, text="Delete Annotation", command=lambda: self.delete_annotation(bbox, dialog)).pack(padx=10, pady=5)
        tk.Button(dialog, text="Change Class", command=lambda: self.change_class(bbox, dialog)).pack(padx=10, pady=5)
        tk.Button(dialog, text="Save and Exit", command=dialog.destroy).pack(padx=10, pady=5)

    def delete_annotation(self, bbox, dialog=None):
        self.annotations.remove(bbox)
        self.save_annotations()
        self.draw_annotations()
        if dialog:
            dialog.destroy()

    def change_class(self, bbox, dialog):
        class_names = list(self.classes.keys())

        change_class_dialog = tk.Toplevel(self.root)
        change_class_dialog.title("Change Class")
        change_class_dialog.geometry(f"+{int(self.root.winfo_rootx() + dialog.winfo_x())}+{int(self.root.winfo_rooty() + dialog.winfo_y())}")

        ttk.Label(change_class_dialog, text="Select class:").pack(padx=10, pady=5)
        class_combobox = ttk.Combobox(change_class_dialog, values=class_names, state="readonly")
        class_combobox.set(class_names[0])
        class_combobox.pack(padx=10, pady=5)

        ttk.Label(change_class_dialog, text="Or add new class:").pack(padx=10, pady=5)
        new_class_entry = tk.Entry(change_class_dialog)
        new_class_entry.pack(padx=10, pady=5)

        def save_new_class():
            new_class_name = new_class_entry.get().strip()
            selected_class_name = class_combobox.get()

            if new_class_name:
                if new_class_name not in self.classes:
                    self.add_class(new_class_name)
                bbox['class_index'] = self.classes[new_class_name]
            else:
                bbox['class_index'] = self.classes[selected_class_name]

            self.save_annotations()
            self.draw_annotations()
            change_class_dialog.destroy()

        tk.Button(change_class_dialog, text="Save", command=save_new_class).pack(padx=10, pady=5)
        tk.Button(change_class_dialog, text="Cancel", command=change_class_dialog.destroy).pack(padx=10, pady=5)

        dialog.destroy

    def add_class(self, class_name):
        if class_name not in self.classes:
            class_index = len(self.classes)
            self.classes[class_name] = class_index
            self.class_colors[class_index] = self.random_color()
            self.populate_class_listbox()

    def mark_as_null(self):
        shutil.move(self.image_path, os.path.join(self.null_folder, os.path.basename(self.image_path)))
        self.next_image()

    def prev_image(self):
        if self.current_image_index > 0:
            self.save_annotations()
            self.current_image_index -= 1
            self.load_image()

    def next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.save_annotations()
            self.current_image_index += 1
            self.load_image()

if __name__ == "__main__":
    root = tk.Tk()
    dataset_path = filedialog.askdirectory(title="Select Dataset Directory")
    if dataset_path:
        app= AnnotationTool(root, dataset_path)
        root.mainloop()