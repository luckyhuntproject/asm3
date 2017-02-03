#!/usr/bin/python

import asm, datetime
import web

"""
Import script for Greyhound rescue database az1307

30th January, 2017
"""

db = web.database( dbn = "mysql", db = "greyhoun_db", user = "root", pw = "root" )

DEFAULT_INTAKE_DATE = datetime.datetime(2010, 01, 01)
DEFAULT_DATE_OF_BIRTH = DEFAULT_INTAKE_DATE
DEFAULT_ADOPTION_DATE = DEFAULT_INTAKE_DATE

def note_fix(s):
    return s.encode("ascii", "xmlcharrefreplace")

# --- START OF CONVERSION ---

owners = []
ownerdonations = []
movements = []
animals = []
logs = []
ppa = {}
ppo = {}

asm.setid("animal", 100)
asm.setid("log", 100)
asm.setid("owner", 100)
asm.setid("ownerdonation", 100)
asm.setid("adoption", 100)

print "\\set ON_ERROR_STOP\nBEGIN;"
print "DELETE FROM internallocation;"
print "DELETE FROM animal WHERE ID >= 100 AND CreatedBy = 'conversion';"
print "DELETE FROM owner WHERE ID >= 100 AND CreatedBy = 'conversion';"
print "DELETE FROM ownerdonation WHERE ID >= 100 AND CreatedBy = 'conversion';"
print "DELETE FROM adoption WHERE ID >= 100 AND CreatedBy = 'conversion';"

# Deal with people first
for d in db.select("members").list():
    # Each row contains a person
    o = asm.Owner()
    owners.append(o)
    ppo[d.id] = o
    o.OwnerForeNames = d.first_name
    o.OwnerSurname = d.last_name
    o.OwnerName = o.OwnerForeNames + " " + o.OwnerSurname
    o.OwnerAddress = d.address_1
    o.OwnerTown = d.address_2
    o.OwnerCounty = d.address_3
    o.OwnerPostcode = d.post_code
    o.EmailAddress = d.email
    o.HomeTelephone = d.phone
    o.IsGiftAid = d.gift_aid
    o.Comments = note_fix(d.notes)

# Secondary members - merge name and telephone number
for d in db.select("secondary_members").list():
    if not ppo.has_key(d.member_id): continue
    o = ppo[d.member_id]
    if d.first_name is not None:
        o.OwnerForeNames += " & " + d.first_name
    if d.last_name is not None and d.last_name != o.OwnerSurname:
        o.OwnerSurname += " & " + d.last_name
    if d.phone is not None:
        o.MobileTelephone = d.phone

# member renewals as payments, record latest renewal date as membership expiry
for d in db.query("select m.*, r.name as renewaltypename from member_renewals m inner join renewal_types r on r.id = m.renewal_type_id;").list():
    if not ppo.has_key(d.member_id): continue
    o = ppo[d.member_id]
    if d.renewed == 1:
        # map renewal type to payment type - only a few so pre-created in their database
        od = asm.OwnerDonation()
        ownerdonations.append(od)
        od.OwnerID = o.ID
        od.Donation = int(d.amount * 100)
        od.Date = d.payment_date
        od.DonationTypeID = asm.donationtype_from_db(d.renewaltypename)
        od.DonationPaymentID = 1 # Cash
        od.IsGiftAid = d.gift_aid
        od.Comments = d.membership_type
        # Is the renewal_date later than the current membership expiry for the person?
        o.IsMember = 1
        if o.MembershipExpiryDate is None or o.MembershipExpiryDate < d.renewal_date:
            o.MembershipExpiryDate = d.renewal_date

# Now dogs
for d in db.query("select d.*, l.name as locationname from dogs d left outer join locations l on l.id = d.location_id").list():
    # Each row contains an animal
    a = asm.Animal()
    animals.append(a)
    ppa[d.id] = a
    has_intake = True
    a.AnimalTypeID = 2
    if d.RGT == 1: a.AnimalTypeID = 43 # RGT
    a.SpeciesID = 1
    a.BaseColourID = asm.colour_id_for_name(d.colour)
    a.AnimalName = d.name
    if a.AnimalName.strip() == "":
        a.AnimalName = "(unknown)"
    a.DateBroughtIn = d.date_of_entry
    if a.DateBroughtIn is None:
        has_intake = False
        a.DateBroughtIn = DEFAULT_INTAKE_DATE
    if d.dob is not None:
        a.DateOfBirth = d.dob
    elif d.date_of_entry is not None and d.approx_age is not None:
        a.DateOfBirth = asm.subtract_days(d.date_of_entry, d.approx_age * 365)
    elif a.DateBroughtIn != DEFAULT_INTAKE_DATE:
        a.DateOfBirth = asm.subtract_days(a.DateBroughtIn, 365*2)
    else:
        a.DateOfBirth = DEFAULT_DATE_OF_BIRTH
    a.CreatedDate = a.DateBroughtIn
    a.LastChangedDate = a.DateBroughtIn
    if d.relinquishment_ownership == 0:
        a.IsTransfer = 1
    a.generateCode()
    a.IsNotAvailableForAdoption = 0
    a.ShelterLocation = asm.location_id_for_name(d.locationname)
    a.Sex = asm.iif(d.sex == "Dog", 1, 0)
    a.Size = 2
    a.Neutered = 1
    a.NeuteredDate = d.neutering_date
    a.IdentichipNumber = d.microchip_no
    if a.IdentichipNumber != "": 
        a.Identichipped = 1
    if d.left_ear_tattoo != "":
        a.Tattoo = 1
        a.TattooNumber = "L:%s R:%s" % (d.left_ear_tattoo, d.right_ear_tattoo)
    a.IsGoodWithCats = 2
    a.IsGoodWithDogs = 2
    a.IsGoodWithChildren = 2
    a.HouseTrained = 0
    a.Archived = 0
    a.EntryReasonID = asm.iif(a.IsTransfer == 1, 15, 17)
    a.ReasonForEntry = d.source
    comments = "RGT: " + asm.iif(d.RGT == 1, "Yes", "No")
    if d.racing_name != "": comments += "\nRacing name: " + d.racing_name
    if d.housed_location != "": comments += "\nHoused Location: " + d.housed_location
    if not has_intake: comments += "\nBlank intake date on original record"
    a.BreedID = asm.iif(d.breed == "Greyhound", 101, 443)
    a.Breed2ID = a.BreedID
    a.BreedName = asm.iif(d.breed == "Greyhound", "Greyhound", "Lurcher")
    a.HiddenAnimalDetails = "%s\n%s" % (comments, note_fix(d.notes))
    if d.deceased == 1:
        a.DeceasedDate = a.DateBroughtIn
        a.PTSReasonID = 2
        a.Archived = 1

# Process fosters first so that the behaviour where we close existing
# movements never closes out a valid adoption
for d in db.select("fostered_dogs"):
    if not ppo.has_key(d.member_id): continue
    if not ppa.has_key(d.dog_id): continue
    a = ppa[d.dog_id]
    o = ppo[d.member_id]
    o.IsFosterer = 1
    m = asm.Movement()
    m.AnimalID = a.ID
    m.OwnerID = o.ID
    m.MovementType = 2
    m.MovementDate = d.date_from
    m.ReturnDate = d.date_to
    if m.ReturnDate is None:
        a.ActiveMovementID = m.ID
        a.ActiveMovementType = 2
        a.ActiveMovementDate = m.MovementDate
    a.LastChangedDate = m.MovementDate
    movements.append(m)

for d in db.select("adopted_dogs"):
    if not ppo.has_key(d.member_id): continue
    if not ppa.has_key(d.dog_id): continue
    a = ppa[d.dog_id]
    o = ppo[d.member_id]
    m = asm.Movement()
    m.AnimalID = a.ID
    m.OwnerID = o.ID
    m.MovementType = 1
    m.MovementDate = d.date_from
    if m.MovementDate is None:
        m.MovementDate = DEFAULT_ADOPTION_DATE
    if a.DateBroughtIn == DEFAULT_INTAKE_DATE and d.date_from is not None:
        a.DateBroughtIn = asm.subtract_days(m.MovementDate, 31*2) # If we have adoption date but no brought in, use adoption - 2 months
    if a.DateOfBirth == DEFAULT_DATE_OF_BIRTH and d.date_from is not None:
        a.DateOfBirth = asm.subtract_days(m.MovementDate, 365*2) # If we have adoption date but no DOB, use adoption - 2 years
    m.ReturnDate = d.date_to
    m.ReturnedReasonID = 4 # Unable to cope
    comments = ""
    if d.date_from is None:
        comments = "Blank adoption date on original record"
    if d.given_name != "":
        comments += "\nGiven name: %s" % d.given_name
    m.Comments = comments
    o.IDCheck = 1
    if m.ReturnDate is None:
        a.Archived = 1
        a.ActiveMovementID = m.ID
        a.ActiveMovementDate = m.MovementDate
        a.ActiveMovementType = 1
    a.LastChangedDate = m.MovementDate
    movements.append(m)
    if d.donation_value > 0:
        od = asm.OwnerDonation()
        ownerdonations.append(od)
        od.OwnerID = o.ID
        od.Donation = int(d.donation_value * 100)
        od.Date = d.date_from
        od.DonationTypeID = 2 # Adoption Fee
        od.DonationPaymentID = 1 # Cash
    if d.rgt_value > 0:
        od = asm.OwnerDonation()
        ownerdonations.append(od)
        od.OwnerID = o.ID
        od.Donation = int(d.donation_value * 100)
        od.Date = d.date_from
        od.DonationTypeID = 10 # RGT
        od.DonationPaymentID = 1 # Cash

# Now that everything else is done, output stored records
for k,v in asm.locations.iteritems():
    print v
for a in animals:
    print a
for o in owners:
    print o
for od in ownerdonations:
    print od
for m in movements:
    print m
for l in logs:
    print l

asm.stderr_summary(animals=animals, logs=logs, ownerdonations=ownerdonations, owners=owners, movements=movements)

print "DELETE FROM configuration WHERE ItemName LIKE 'DBView%';"
print "COMMIT;"
