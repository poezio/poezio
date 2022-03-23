// This file is part of Poezio.
//
// Poezio is free software: you can redistribute it and/or modify
// it under the terms of the GPL-3.0-or-later license. See the COPYING file.

mod sticker;

use gtk::prelude::*;
use sticker::StickerType as Sticker;

fn main() {
    let app = gtk::Application::builder()
        .application_id("io.poez.StickerPicker")
        .flags(gio::ApplicationFlags::HANDLES_OPEN)
        .build();

    let quit = gio::SimpleAction::new("quit", None);
    app.set_accels_for_action("app.quit", &["<Control>q"]);
    app.add_action(&quit);
    quit.connect_activate(glib::clone!(@weak app => move |_, _| app.quit()));

    app.connect_open(move |app, directories, _| {
        let path = match directories {
            [directory] => directory.path().unwrap(),
            _ => {
                eprintln!("Only a single directory is allowed!");
                std::process::exit(1);
            }
        };

        let window = gtk::ApplicationWindow::builder()
            .application(app)
            .default_width(1280)
            .default_height(720)
            .title("Poezio Sticker Picker")
            .build();

        let sw = gtk::ScrolledWindow::builder()
            .has_frame(true)
            .hscrollbar_policy(gtk::PolicyType::Always)
            .vscrollbar_policy(gtk::PolicyType::Always)
            .vexpand(true)
            .build();
        window.set_child(Some(&sw));

        let store = gio::ListStore::new(Sticker::static_type());

        for dir_entry in std::fs::read_dir(path).unwrap() {
            let dir_entry = dir_entry.unwrap();
            let file_name = dir_entry.file_name().into_string().unwrap();
            let sticker = Sticker::new(file_name, &dir_entry.path());
            store.append(&sticker);
        }

        let factory = gtk::SignalListItemFactory::new();
        factory.connect_setup(|_, item| {
            let picture = gtk::Picture::builder()
                .alternative_text("Sticker")
                .can_shrink(false)
                .build();
            item.set_child(Some(&picture));
        });
        factory.connect_bind(|_, list_item| {
            if let Some(child) = list_item.child() {
                if let Some(item) = list_item.item() {
                    let picture: gtk::Picture = child.downcast().unwrap();
                    let sticker: Sticker = item.downcast().unwrap();
                    picture.set_paintable(sticker.texture().as_ref());
                }
            }
        });

        let selection = gtk::SingleSelection::new(Some(&store));
        let grid_view = gtk::GridView::builder()
            .single_click_activate(true)
            .model(&selection)
            .factory(&factory)
            .build();
        grid_view.connect_activate(move |_, position| {
            let item = store.item(position).unwrap();
            let sticker: Sticker = item.downcast().unwrap();
            if let Some(filename) = sticker.filename() {
                println!("{}", filename);
                std::process::exit(0);
            }
        });
        sw.set_child(Some(&grid_view));

        window.show();
    });

    app.run();
}
