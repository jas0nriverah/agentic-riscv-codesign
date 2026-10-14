(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x129 (bvshl y (_ bv9 32))))
(let ((?x125 (bvshl x (_ bv9 32))))
(let ((?x132 (bvsub ?x125 ?x129)))
(let ((?x24 (bvsub x y)))
(let ((?x131 (bvshl ?x24 (_ bv9 32))))
(and (distinct ?x131 ?x132) true)))))))
(check-sat)
