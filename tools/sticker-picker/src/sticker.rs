// This file is part of Poezio.
//
// Poezio is free software: you can redistribute it and/or modify
// it under the terms of the GPL-3.0-or-later license. See the COPYING file.

use gtk::prelude::*;
use gtk::subclass::prelude::*;
use std::cell::RefCell;
use std::path::Path;

#[derive(Debug, Default)]
pub struct Sticker {
    filename: RefCell<Option<String>>,
    texture: RefCell<Option<gdk::Texture>>,
}

#[glib::object_subclass]
impl ObjectSubclass for Sticker {
    const NAME: &'static str = "Sticker";
    type Type = StickerType;
}

impl ObjectImpl for Sticker {
    fn properties() -> &'static [glib::ParamSpec] {
        use once_cell::sync::Lazy;
        static PROPERTIES: Lazy<Vec<glib::ParamSpec>> = Lazy::new(|| {
            vec![
                glib::ParamSpecString::new(
                    "filename",
                    "Filename",
                    "Filename",
                    None,
                    glib::ParamFlags::READWRITE | glib::ParamFlags::CONSTRUCT_ONLY,
                ),
                glib::ParamSpecObject::new(
                    "texture",
                    "Texture",
                    "Texture",
                    gdk::Texture::static_type(),
                    glib::ParamFlags::READWRITE | glib::ParamFlags::CONSTRUCT_ONLY,
                ),
            ]
        });
        PROPERTIES.as_ref()
    }

    fn set_property(
        &self,
        _obj: &StickerType,
        _id: usize,
        value: &glib::Value,
        pspec: &glib::ParamSpec,
    ) {
        match pspec.name() {
            "filename" => {
                let filename = value.get().unwrap();
                self.filename.replace(filename);
            }
            "texture" => {
                let texture = value.get().unwrap();
                self.texture.replace(texture);
            }
            _ => unimplemented!(),
        }
    }

    fn property(&self, _obj: &StickerType, _id: usize, pspec: &glib::ParamSpec) -> glib::Value {
        match pspec.name() {
            "filename" => self.filename.borrow().to_value(),
            "texture" => self.texture.borrow().to_value(),
            _ => unimplemented!(),
        }
    }
}

glib::wrapper! {
    pub struct StickerType(ObjectSubclass<Sticker>);
}

impl StickerType {
    pub fn new(filename: String, path: &Path) -> StickerType {
        let texture = gdk::Texture::from_filename(path).unwrap();
        glib::Object::new(&[("filename", &filename), ("texture", &texture)])
            .expect("Failed to create Sticker")
    }

    pub fn filename(&self) -> Option<String> {
        let imp = self.imp();
        let filename = imp.filename.borrow();
        if let Some(filename) = filename.as_ref() {
            Some(filename.clone())
        } else {
            None
        }
    }

    pub fn texture(&self) -> Option<gdk::Texture> {
        let imp = self.imp();
        let texture = imp.texture.borrow();
        if let Some(texture) = texture.as_ref() {
            Some(texture.clone())
        } else {
            None
        }
    }
}
