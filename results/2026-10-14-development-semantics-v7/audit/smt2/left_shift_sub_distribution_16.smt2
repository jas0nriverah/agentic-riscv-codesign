(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x191 (bvshl y (_ bv16 32))))
(let ((?x187 (bvshl x (_ bv16 32))))
(let ((?x194 (bvsub ?x187 ?x191)))
(let ((?x24 (bvsub x y)))
(let ((?x193 (bvshl ?x24 (_ bv16 32))))
(and (distinct ?x193 ?x194) true)))))))
(check-sat)
