(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x218 (bvshl y (_ bv19 32))))
(let ((?x214 (bvshl x (_ bv19 32))))
(let ((?x221 (bvsub ?x214 ?x218)))
(let ((?x24 (bvsub x y)))
(let ((?x220 (bvshl ?x24 (_ bv19 32))))
(and (distinct ?x220 ?x221) true)))))))
(check-sat)
