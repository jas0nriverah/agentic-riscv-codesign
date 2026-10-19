(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x209 (bvshl y (_ bv18 32))))
(let ((?x205 (bvshl x (_ bv18 32))))
(let ((?x212 (bvsub ?x205 ?x209)))
(let ((?x24 (bvsub x y)))
(let ((?x211 (bvshl ?x24 (_ bv18 32))))
(and (distinct ?x211 ?x212) true)))))))
(check-sat)
