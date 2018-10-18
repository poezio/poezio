use std::str::FromStr;
use chrono::{DateTime, Utc, TimeZone};
use nom;

pub trait LogItem {
    fn get_time(&self) -> &DateTime<Utc>;
    fn get_message(&self) -> String;
}

#[derive(Debug, PartialEq)]
pub struct LogInfo<'a> {
    time: DateTime<Utc>,
    message: Vec<&'a str>,
}

impl<'a> LogItem for LogInfo<'a> {
    fn get_time(&self) -> &DateTime<Utc> {
        &self.time
    }

    fn get_message(&self) -> String {
        self.message.join("\n")
    }
}

#[derive(Debug, PartialEq)]
pub struct LogMessage<'a> {
    time: DateTime<Utc>,
    nick: &'a str,
    message: Vec<&'a str>,
}

impl<'a> LogMessage<'a> {
    pub fn get_nick(&self) -> &str {
        self.nick
    }
}

impl<'a> LogItem for LogMessage<'a> {
    fn get_time(&self) -> &DateTime<Utc> {
        &self.time
    }

    fn get_message(&self) -> String {
        self.message.join("\n")
    }
}

named!(
    datetime<&str, DateTime<Utc>>,
    do_parse!(
        year: map_res!(take!(4), i32::from_str) >>
        month: map_res!(take!(2), u32::from_str) >>
        day: map_res!(take!(2), u32::from_str) >>
        tag!("T") >>
        hour: map_res!(take!(2), u32::from_str) >>
        tag!(":") >>
        minute: map_res!(take!(2), u32::from_str) >>
        tag!(":") >>
        second: map_res!(take!(2), u32::from_str) >>
        tag!("Z") >>
        (Utc.ymd(year, month, day).and_hms(hour, minute, second))
    )
);

named!(
    pub parse_log_info<&str, LogInfo>,
    do_parse!(
        tag!("MI ") >>
        time: datetime >>
        tag!(" ") >>
        nb_lines: map_res!(take!(3), usize::from_str) >>
        tag!(" ") >>
        line0: take_until_and_consume!("\n") >>
        message: many_m_n!(nb_lines, nb_lines, do_parse!(
            tag!(" ") >>
            line: take_until_and_consume!("\n") >>
            (line)
        )) >>
        (LogInfo {
            time,
            message: {
                let mut message = message;
                message.insert(0, line0);
                message
            },
        })
    )
);

named!(
    pub parse_log_message<&str, LogMessage>,
    do_parse!(
        tag!("MR ") >>
        time: datetime >>
        tag!(" ") >>
        nb_lines: map_res!(take!(3), usize::from_str) >>
        tag!(" <") >>
        nick: take_until_and_consume!(">  ") >>
        line0: take_until_and_consume!("\n") >>
        message: many_m_n!(nb_lines, nb_lines, do_parse!(
            tag!(" ") >>
            line: take_until_and_consume!("\n") >>
            (line)
        )) >>
        (LogMessage {
            time,
            nick,
            message: {
                let mut message = message;
                message.insert(0, line0);
                message
            },
        })
    )
);

#[derive(Debug, PartialEq)]
pub enum Item<'a> {
    Message(LogMessage<'a>),
    Info(LogInfo<'a>),
}

pub fn parse_logs(mut logs: &str) -> Result<Vec<Item>, nom::Err<&str>> {
    let mut items = vec![];
    loop {
        if logs.is_empty() {
            break;
        }
        if logs.starts_with("MR ") {
            let message = parse_log_message(logs)?;
            logs = message.0;
            items.push(Item::Message(message.1));
        } else if logs.starts_with("MI ") {
            let info = parse_log_info(logs)?;
            logs = info.0;
            items.push(Item::Info(info.1));
        } else {
            return Err(nom::Err::Error(nom::Context::Code(logs, nom::ErrorKind::Custom(1))));
        }
    }
    Ok(items)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn simple_message() {
        let log = "MR 20181016T14:10:08Z 000 <Link Mauve>  Hello world!\n";
        let message = LogMessage {
            time: "2018-10-16T16:10:08+0200".parse().unwrap(),
            nick: "Link Mauve",
            message: vec!["Hello world!"],
        };
        let message2 = parse_log_message(log).unwrap();
        assert_eq!(message, message2.1);
    }

    #[test]
    fn multiple_messages() {
        let log = "MR 20181016T14:10:08Z 000 <Link Mauve>  Hello…\nMR 20181016T14:10:11Z 000 <Link Mauve>  world!\n";
        let messages = [
            LogMessage {
                time: "2018-10-16T16:10:08+0200".parse().unwrap(),
                nick: "Link Mauve",
                message: vec!["Hello…"],
            },
            LogMessage {
                time: "2018-10-16T16:10:11+0200".parse().unwrap(),
                nick: "Link Mauve",
                message: vec!["world!"],
            }
        ];
        let message1 = parse_log_message(log).unwrap();
        let message2 = parse_log_message(message1.0).unwrap();
        assert_eq!(messages, [message1.1, message2.1]);
    }

    #[test]
    fn parse_all_logs() {
        let log = "MR 20181016T14:10:08Z 000 <Link Mauve>  Hello…\nMR 20181016T14:10:11Z 000 <Link Mauve>  world!\n";
        let messages = vec![
            Item::Message(LogMessage {
                time: "2018-10-16T16:10:08+0200".parse().unwrap(),
                nick: "Link Mauve",
                message: vec!["Hello…"],
            }),
            Item::Message(LogMessage {
                time: "2018-10-16T16:10:11+0200".parse().unwrap(),
                nick: "Link Mauve",
                message: vec!["world!"],
            })
        ];
        let messages1 = parse_logs(log).unwrap();
        assert_eq!(messages, messages1);
    }

    #[test]
    fn trailing_characters() {
        let log = "MR 20181016T14:10:08Z 000 <Link Mauve>  Hello…\nMR 20181016T14:10:11Z 000 <Link Mauve>  world!\n\n";
        parse_logs(log).unwrap_err();
    }

    #[test]
    fn multiline_message() {
        let log = "MR 20181016T14:10:08Z 001 <Link Mauve>  Hello…\n world!\n";
        let message = LogMessage {
            time: "2018-10-16T16:10:08+0200".parse().unwrap(),
            nick: "Link Mauve",
            message: vec!["Hello…", "world!"],
        };
        let message2 = parse_log_message(log).unwrap();
        assert_eq!(message, message2.1);
    }
}
