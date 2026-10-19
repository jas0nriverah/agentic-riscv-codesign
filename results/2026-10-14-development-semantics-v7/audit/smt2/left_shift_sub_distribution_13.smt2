(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x165 (bvshl y (_ bv13 32))))
(let ((?x161 (bvshl x (_ bv13 32))))
(let ((?x168 (bvsub ?x161 ?x165)))
(let ((?x24 (bvsub x y)))
(let ((?x167 (bvshl ?x24 (_ bv13 32))))
(and (distinct ?x167 ?x168) true)))))))
(check-sat)
