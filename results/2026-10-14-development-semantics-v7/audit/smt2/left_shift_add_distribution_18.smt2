(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x209 (bvshl y (_ bv18 32))))
(let ((?x205 (bvshl x (_ bv18 32))))
(let ((?x210 (bvadd ?x205 ?x209)))
(let ((?x19 (bvadd x y)))
(let ((?x208 (bvshl ?x19 (_ bv18 32))))
(and (distinct ?x208 ?x210) true)))))))
(check-sat)
